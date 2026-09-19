"""RDS登録管理 (REQ-H04, ⑨「RDS登録管理」メニュー)。

同一ゾーンRDS(Query API送信先, シングルトン)と他ゾーンRDS(Registration API送信先,
AliasNode単位で複数)を管理する。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas import domain
from app.services import registration_engine, same_zone_sync

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rds-config"])

MIN_SOURCE_PORT = 1024
MAX_SOURCE_PORT = 65535


def _validate_source_port(db: Session, source_port: int | None, exclude_id: str | None = None) -> None:
    """registration_source_port(REQ-E07)の範囲チェックと重複チェックを行う。

    重複チェックは、登録先(registration_ip_address)が設定済みの有効な
    ZoneRdsConfig全件を対象とする。
    """
    if source_port is None:
        return
    if not (MIN_SOURCE_PORT <= source_port <= MAX_SOURCE_PORT):
        logger.warning("Rejected registration_source_port %s: out of range", source_port)
        raise HTTPException(
            status_code=400,
            detail=f"送信元ポート番号は{MIN_SOURCE_PORT}〜{MAX_SOURCE_PORT}の範囲で指定してください",
        )

    query = db.query(models.ZoneRdsConfig).filter(
        models.ZoneRdsConfig.registration_source_port == source_port,
        models.ZoneRdsConfig.registration_ip_address != "",
    )
    if exclude_id is not None:
        query = query.filter(models.ZoneRdsConfig.id != exclude_id)
    conflict = query.first()
    if conflict is not None:
        logger.warning(
            "Rejected registration_source_port %s: already used by ZoneRdsConfig %s", source_port, conflict.id
        )
        raise HTTPException(
            status_code=409,
            detail=f"送信元ポート {source_port} は既に他のRDS設定で使用されています",
        )


@router.get("/same-zone-rds", response_model=domain.SameZoneRdsConfigOut)
def get_same_zone_rds(db: Session = Depends(get_db)):
    config = db.query(models.SameZoneRdsConfig).first()
    if config is None:
        config = models.SameZoneRdsConfig()
        db.add(config)
        db.commit()
    out = domain.SameZoneRdsConfigOut.model_validate(config)
    out.connection_status = "online" if same_zone_sync.status.connected else "offline"
    return out


@router.put("/same-zone-rds", response_model=domain.SameZoneRdsConfigOut)
def update_same_zone_rds(payload: domain.SameZoneRdsConfigIn, db: Session = Depends(get_db)):
    config = db.query(models.SameZoneRdsConfig).first()
    if config is None:
        config = models.SameZoneRdsConfig()
        db.add(config)
    config.enabled = payload.enabled
    config.ip_address = payload.ip_address
    config.port = payload.port
    config.query_api_version = payload.query_api_version
    db.commit()
    out = domain.SameZoneRdsConfigOut.model_validate(config)
    out.connection_status = "online" if same_zone_sync.status.connected else "offline"
    return out


@router.get("/zone-rds-configs", response_model=list[domain.ZoneRdsConfigOut])
def list_zone_rds_configs(node_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ZoneRdsConfig)
    if node_id:
        query = query.filter(models.ZoneRdsConfig.node_id == node_id)
    results = []
    for cfg in query.all():
        out = domain.ZoneRdsConfigOut.model_validate(cfg)
        st = registration_engine.zone_status.get(cfg.id)
        out.connection_status = "online" if (st and st.connected) else "offline"
        results.append(out)
    return results


@router.post("/zone-rds-configs", response_model=domain.ZoneRdsConfigOut, status_code=201)
def create_zone_rds_config(payload: domain.ZoneRdsConfigIn, db: Session = Depends(get_db)):
    node = db.get(models.AliasNode, payload.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="AliasNode not found")
    _validate_source_port(db, payload.registration_source_port)

    config = models.ZoneRdsConfig(**payload.model_dump())
    db.add(config)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This RDS (ip:port) is already bound to another AliasNode (REQ-B03 exclusive control)",
        ) from exc
    return domain.ZoneRdsConfigOut.model_validate(config)


@router.put("/zone-rds-configs/{config_id}", response_model=domain.ZoneRdsConfigOut)
def update_zone_rds_config(config_id: str, payload: domain.ZoneRdsConfigIn, db: Session = Depends(get_db)):
    config = db.get(models.ZoneRdsConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="ZoneRdsConfig not found")
    _validate_source_port(db, payload.registration_source_port, exclude_id=config_id)
    for field, value in payload.model_dump().items():
        setattr(config, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This RDS (ip:port) is already bound to another AliasNode") from exc
    return domain.ZoneRdsConfigOut.model_validate(config)


@router.delete("/zone-rds-configs/{config_id}", status_code=204)
def delete_zone_rds_config(config_id: str, db: Session = Depends(get_db)):
    config = db.get(models.ZoneRdsConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="ZoneRdsConfig not found")
    db.delete(config)
    db.commit()
