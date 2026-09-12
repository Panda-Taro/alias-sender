"""AliasSenderの作成・SDP同期・オフライン検知カスケードロジック (⑦③, ⑩-6, REQ-D/A系)。

ユニットテストで直接呼び出せるよう、DBアクセスを含む純粋な関数として実装する。
"""

import logging

from sqlalchemy.orm import Session

from app.db import models
from app.services.sdp_utils import detect_media_type

logger = logging.getLogger(__name__)

MEDIA_SUFFIX = {"video": "V", "audio": "A", "ancillary": "ANC"}


def build_label(connector_label: str, media_type: str) -> str:
    return f"{connector_label}_{MEDIA_SUFFIX[media_type]}"


class AliasSenderError(ValueError):
    pass


def create_alias_sender(
    db: Session,
    connector_id: str,
    real_sender_id: str,
    media_type: str | None,
    description: str,
) -> models.AliasSender:
    connector = db.get(models.AliasConnector, connector_id)
    if connector is None:
        raise AliasSenderError("AliasConnector not found")

    real_sender = db.get(models.RealSender, real_sender_id)
    if real_sender is None:
        raise AliasSenderError("RealSender not found")

    resolved_media_type = media_type or real_sender.media_type_detected
    if resolved_media_type not in MEDIA_SUFFIX:
        raise AliasSenderError("media_type could not be determined; specify it explicitly")

    sibling_count = (
        db.query(models.AliasSender).filter(models.AliasSender.connector_id == connector_id).count()
    )
    duplicate = (
        db.query(models.AliasSender)
        .filter(
            models.AliasSender.connector_id == connector_id,
            models.AliasSender.media_type == resolved_media_type,
        )
        .first()
    )
    if duplicate:
        raise AliasSenderError(
            f"AliasConnector already has a {resolved_media_type} AliasSender (max 3, one per media type)"
        )
    if sibling_count >= 3:
        raise AliasSenderError("AliasConnector already has 3 AliasSenders (V/A/ANC max)")

    alias_sender = models.AliasSender(
        connector_id=connector_id,
        real_sender_id=real_sender_id,
        label=build_label(connector.connector_label, resolved_media_type),
        description=description,
        media_type=resolved_media_type,
        sdp_mirrored=real_sender.sdp_raw,
        sync_status=real_sender.status,
    )
    db.add(alias_sender)
    db.flush()
    return alias_sender


def update_alias_sender_connector(db: Session, alias_sender: models.AliasSender, new_connector_id: str) -> None:
    """REQ-D02: 紐づけ先AliasConnectorの変更。labelは新Connectorのlabelで再生成する。"""
    connector = db.get(models.AliasConnector, new_connector_id)
    if connector is None:
        raise AliasSenderError("AliasConnector not found")

    existing = (
        db.query(models.AliasSender)
        .filter(
            models.AliasSender.connector_id == new_connector_id,
            models.AliasSender.media_type == alias_sender.media_type,
            models.AliasSender.id != alias_sender.id,
        )
        .first()
    )
    if existing:
        raise AliasSenderError(
            f"Target AliasConnector already has a {alias_sender.media_type} AliasSender"
        )

    alias_sender.connector_id = new_connector_id
    alias_sender.label = build_label(connector.connector_label, alias_sender.media_type)


def propagate_sdp_update(db: Session, real_sender: models.RealSender) -> None:
    """REQA05/REQD08: RealSenderのSDP更新を、紐づく全AliasSenderへリアルタイム反映する。"""
    for alias_sender in real_sender.alias_senders:
        alias_sender.sdp_mirrored = real_sender.sdp_raw
        alias_sender.last_synced_at = real_sender.last_seen_at


def set_real_sender_offline(db: Session, real_sender: models.RealSender) -> None:
    """REQA06: Sender消失検知時、RealSenderと紐づく全AliasSenderをoffline化する。"""
    real_sender.status = "offline"
    for alias_sender in real_sender.alias_senders:
        alias_sender.sync_status = "offline"
    logger.warning("RealSender %s (%s) went offline", real_sender.id, real_sender.nmos_sender_label)


def set_real_sender_online(db: Session, real_sender: models.RealSender, sdp_raw: str) -> None:
    """REQA07: Sender復活検知時、RealSenderと紐づく全AliasSenderをonline化しSDPを再同期する。"""
    real_sender.status = "online"
    real_sender.sdp_raw = sdp_raw
    real_sender.media_type_detected = detect_media_type(sdp_raw)
    for alias_sender in real_sender.alias_senders:
        alias_sender.sync_status = "online"
        alias_sender.sdp_mirrored = sdp_raw
    logger.info("RealSender %s (%s) is back online", real_sender.id, real_sender.nmos_sender_label)
