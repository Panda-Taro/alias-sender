"""ダッシュボード用の集約API (REQ-H01〜H03)。"""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas import domain
from app.services import registration_engine, same_zone_sync
from app.services.scope import get_node_scope

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/rds-status")
def rds_status(db: Session = Depends(get_db)):
    same_zone_config = db.query(models.SameZoneRdsConfig).first()
    zone_configs = db.query(models.ZoneRdsConfig).all()

    return {
        "same_zone": {
            "enabled": bool(same_zone_config and same_zone_config.enabled),
            "ip_address": same_zone_config.ip_address if same_zone_config else "",
            "port": same_zone_config.port if same_zone_config else None,
            "query_api_version": same_zone_config.query_api_version if same_zone_config else "",
            "connected": same_zone_sync.status.connected,
            "ws_connected": same_zone_sync.status.ws_connected,
            "last_error": same_zone_sync.status.last_error,
        },
        "other_zones": [
            {
                "id": cfg.id,
                "node_id": cfg.node_id,
                "ip_address": cfg.registration_ip_address,
                "port": cfg.registration_port,
                "registration_api_version": cfg.registration_api_version,
                "enabled": cfg.registration_api_enabled,
                "connected": (
                    registration_engine.zone_status[cfg.id].connected
                    if cfg.id in registration_engine.zone_status
                    else False
                ),
                "last_error": (
                    registration_engine.zone_status[cfg.id].last_error
                    if cfg.id in registration_engine.zone_status
                    else None
                ),
            }
            for cfg in zone_configs
        ],
    }


@router.get("/same-zone-tree")
def same_zone_tree(db: Session = Depends(get_db)):
    """REQ-H02: 同一ゾーンRDSから取得したNode一覧とDevice/Sender状態。Receiverは常に空。"""
    real_senders = db.query(models.RealSender).all()
    nodes: dict[str, dict] = {}
    for rs in real_senders:
        node = nodes.setdefault(
            rs.nmos_node_id or "unknown",
            {"nmos_node_id": rs.nmos_node_id, "devices": {}},
        )
        device = node["devices"].setdefault(
            rs.nmos_device_id or "unknown",
            {"nmos_device_id": rs.nmos_device_id, "senders": [], "receivers": []},
        )
        device["senders"].append(domain.RealSenderOut.model_validate(rs))

    out = []
    for node_id, node in nodes.items():
        out.append({"nmos_node_id": node_id, "devices": list(node["devices"].values())})
    return out


@router.get("/alias-node-tree", response_model=list[domain.NodeTreeOut])
def alias_node_tree(db: Session = Depends(get_db)):
    """REQ-H03: Alias Device一覧→Connector→3つのAlias Senderの同期状態。"""
    result = []
    for node in db.query(models.AliasNode).all():
        scope = get_node_scope(db, node.id)
        connectors_by_device: dict[str, list] = defaultdict(list)
        for connector in scope.connectors:
            connectors_by_device[connector.device_id].append(
                domain.ConnectorWithSenders(
                    id=connector.id,
                    connector_label=connector.connector_label,
                    senders=[domain.AliasSenderOut.model_validate(s) for s in connector.senders],
                )
            )
        devices = [
            domain.DeviceWithConnectors(
                id=d.id,
                alias_device_label=d.alias_device_label,
                alias_device_description=d.alias_device_description,
                connectors=connectors_by_device.get(d.id, []),
            )
            for d in scope.devices
        ]
        zone_configs = [domain.ZoneRdsConfigOut.model_validate(c) for c in node.zone_rds_configs]
        result.append(
            domain.NodeTreeOut(node=domain.AliasNodeOut.model_validate(node), devices=devices, zone_rds_configs=zone_configs)
        )
    return result
