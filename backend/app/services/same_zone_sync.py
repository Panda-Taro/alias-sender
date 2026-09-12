"""同一ゾーンRDS連携エンジン (REQ-A01〜A07)。

Query APIでのポーリングを基本としつつ、WebSocket Subscriptionからの通知を
即時reconcileのトリガーとして使う(詳細はDECISIONS.md参照)。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import websockets

from app.config import settings
from app.db import models
from app.db.database import get_session
from app.services import alias_sender_logic
from app.services.nmos_query_client import NmosQueryClient
from app.services.sdp_utils import detect_media_type

logger = logging.getLogger(__name__)


@dataclass
class SameZoneStatus:
    enabled: bool = False
    connected: bool = False
    ws_connected: bool = False
    ip_address: str = ""
    port: int | None = None
    version: str = "v1.3"
    last_error: str | None = None
    last_reconciled_at: datetime | None = None


status = SameZoneStatus()


class SameZoneSyncEngine:
    def __init__(self) -> None:
        self._poll_task: asyncio.Task | None = None
        self._ws_task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._stopping = True
        for task in (self._poll_task, self._ws_task):
            if task:
                task.cancel()
        self._poll_task = None
        self._ws_task = None

    async def _poll_loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                logger.exception("same-zone RDS sync tick failed")
            await asyncio.sleep(settings.query_poll_interval_seconds)

    async def _tick(self) -> None:
        db = get_session()
        try:
            config = db.query(models.SameZoneRdsConfig).first()
            if config is None or not config.enabled or not config.ip_address or not config.port:
                status.enabled = bool(config and config.enabled)
                status.connected = False
                return

            status.enabled = True
            status.ip_address = config.ip_address
            status.port = config.port
            status.version = config.query_api_version

            client = NmosQueryClient(config.ip_address, config.port, config.query_api_version)
            await reconcile(db, client)
            db.commit()
            status.connected = True
            status.last_error = None
            status.last_reconciled_at = datetime.now(timezone.utc)

            # (Re)start the websocket listener if not already running
            if self._ws_task is None or self._ws_task.done():
                self._ws_task = asyncio.create_task(self._ws_loop(client))
        except Exception as exc:  # noqa: BLE001
            status.connected = False
            status.last_error = str(exc)
            db.rollback()
            raise
        finally:
            db.close()

    async def _ws_loop(self, client: NmosQueryClient) -> None:
        backoff = 1.0
        while not self._stopping:
            try:
                sub = await client.create_subscription()
                ws_href = sub.get("ws_href")
                if not ws_href:
                    logger.warning("Query API subscription returned no ws_href; retrying later")
                    status.ws_connected = False
                    return
                async with websockets.connect(ws_href) as ws:
                    status.ws_connected = True
                    backoff = 1.0
                    logger.info("WebSocket subscription connected: %s", ws_href)
                    async for _message in ws:
                        # REQ-A04: メッセージ受信をトリガーに即時reconcile
                        try:
                            await self._tick()
                        except Exception:  # noqa: BLE001
                            logger.exception("reconcile after WS notification failed")
            except (asyncio.CancelledError,):
                raise
            except Exception as exc:  # noqa: BLE001
                status.ws_connected = False
                logger.warning("WebSocket subscription error: %s; reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)


async def reconcile(db, client: NmosQueryClient) -> None:
    """REQ-A01〜A03, A06, A07: Query APIから一覧を取得し、RealSenderテーブルと同期する。"""
    senders = await client.get_senders()
    devices = await client.get_devices()
    device_to_node = {d["id"]: d.get("node_id", "") for d in devices}
    seen_ids: set[str] = set()

    for sender in senders:
        nmos_sender_id = sender["id"]
        seen_ids.add(nmos_sender_id)
        device_id = sender.get("device_id", "")
        node_id = device_to_node.get(device_id, "")

        real_sender = (
            db.query(models.RealSender)
            .filter(models.RealSender.nmos_sender_id == nmos_sender_id)
            .first()
        )

        manifest_href = sender.get("manifest_href")
        sdp_raw = ""
        if manifest_href:
            try:
                sdp_raw = await client.fetch_manifest(manifest_href)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to fetch manifest for sender %s", nmos_sender_id)

        if real_sender is None:
            real_sender = models.RealSender(
                nmos_node_id=node_id,
                nmos_device_id=device_id,
                nmos_sender_id=nmos_sender_id,
                nmos_sender_label=sender.get("label", nmos_sender_id),
                sdp_raw=sdp_raw,
                media_type_detected=detect_media_type(sdp_raw),
                status="online",
                last_seen_at=datetime.now(timezone.utc),
            )
            db.add(real_sender)
            db.flush()
        else:
            real_sender.nmos_sender_label = sender.get("label", real_sender.nmos_sender_label)
            real_sender.nmos_device_id = device_id
            real_sender.nmos_node_id = node_id
            real_sender.last_seen_at = datetime.now(timezone.utc)
            was_offline = real_sender.status == "offline"
            sdp_changed = sdp_raw and sdp_raw != real_sender.sdp_raw

            if was_offline:
                alias_sender_logic.set_real_sender_online(db, real_sender, sdp_raw or real_sender.sdp_raw)
            elif sdp_changed:
                real_sender.sdp_raw = sdp_raw
                real_sender.media_type_detected = detect_media_type(sdp_raw)
                alias_sender_logic.propagate_sdp_update(db, real_sender)

    # REQ-A06: 一覧から消えたRealSenderをoffline化する
    all_real_senders = db.query(models.RealSender).all()
    for real_sender in all_real_senders:
        if real_sender.nmos_sender_id not in seen_ids and real_sender.status == "online":
            alias_sender_logic.set_real_sender_offline(db, real_sender)


engine = SameZoneSyncEngine()
