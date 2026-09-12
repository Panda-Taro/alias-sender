"""AliasNodeごとに動的ポートで起動するNode API(IS-04サーバー)+
Connection API(IS-05サーバー) (REQ-F/G, ⑪4-④⑤)。

`create_node_app(node_id)`でnode_idをクロージャに束縛したFastAPIサブアプリを
生成し、NodePortServerManagerがAliasNode.node_api_portでuvicorn.Serverとして
個別に起動する。
"""

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.nmos import resources
from app.services.host_info import get_primary_ip
from app.services.scope import find_sender_in_scope, get_node_scope
from app.services.sdp_utils import parse_transport_params

logger = logging.getLogger(__name__)

IS04_VERSIONS = {"v1.1", "v1.2", "v1.3"}
IS05_VERSIONS = {"v1.0", "v1.1"}

# In-memory master_enable state per (node_id, sender_id) - PoC only, not persisted.
_active_state: dict[str, bool] = {}


def _check_version(version: str, allowed: set[str]) -> None:
    if version not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported API version: {version}")


def create_node_app(node_id: str) -> FastAPI:
    app = FastAPI(title=f"Alias Node {node_id}")

    def _scope_or_404(db: Session):
        scope = get_node_scope(db, node_id)
        if scope is None:
            raise HTTPException(status_code=404, detail="AliasNode not found")
        return scope

    @app.get("/x-nmos/node/{version}/self")
    def node_self(version: str, request: Request, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        host = get_primary_ip()
        port = request.url.port or scope.node.node_api_port
        return resources.build_node_resource(scope.node, host, port)

    @app.get("/x-nmos/node/{version}/devices")
    def node_devices(version: str, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        sender_ids_by_device: dict[str, list[str]] = {d.id: [] for d in scope.devices}
        for connector in scope.connectors:
            for s in connector.senders:
                sender_ids_by_device.setdefault(connector.device_id, []).append(s.id)
        return [
            resources.build_device_resource(d, node_id, sender_ids_by_device.get(d.id, []))
            for d in scope.devices
        ]

    @app.get("/x-nmos/node/{version}/sources")
    def node_sources(version: str, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        device_by_connector = {c.id: c.device_id for c in scope.connectors}
        out = []
        for connector in scope.connectors:
            for s in connector.senders:
                out.append(resources.build_source_resource(s, device_by_connector[connector.id]))
        return out

    @app.get("/x-nmos/node/{version}/sources/{source_id}")
    def node_source_detail(version: str, source_id: str, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        device_by_connector = {c.id: c.device_id for c in scope.connectors}
        for connector in scope.connectors:
            for s in connector.senders:
                if s.source_id == source_id:
                    return resources.build_source_resource(s, device_by_connector[connector.id])
        raise HTTPException(status_code=404, detail="Source not found in this AliasNode scope")

    @app.get("/x-nmos/node/{version}/senders")
    def node_senders(version: str, request: Request, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        device_by_connector = {c.id: c.device_id for c in scope.connectors}
        host = get_primary_ip()
        port = request.url.port or scope.node.node_api_port
        out = []
        for connector in scope.connectors:
            for s in connector.senders:
                out.append(
                    resources.build_sender_resource(s, device_by_connector[connector.id], host, port, version)
                )
        return out

    @app.get("/x-nmos/node/{version}/senders/{sender_id}")
    def node_sender_detail(version: str, sender_id: str, request: Request, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        sender = find_sender_in_scope(scope, sender_id)
        if sender is None:
            raise HTTPException(status_code=404, detail="Sender not found in this AliasNode scope")
        device_by_connector = {c.id: c.device_id for c in scope.connectors}
        connector_id = sender.connector_id
        host = get_primary_ip()
        port = request.url.port or scope.node.node_api_port
        return resources.build_sender_resource(sender, device_by_connector[connector_id], host, port, version)

    @app.get("/x-nmos/node/{version}/senders/{sender_id}/transportfile")
    def node_sender_transportfile(version: str, sender_id: str, db: Session = Depends(get_db)):
        _check_version(version, IS04_VERSIONS)
        scope = _scope_or_404(db)
        sender = find_sender_in_scope(scope, sender_id)
        if sender is None:
            raise HTTPException(status_code=404, detail="Sender not found in this AliasNode scope")
        return Response(content=sender.sdp_mirrored, media_type="application/sdp")

    @app.get("/x-nmos/node/{version}/receivers")
    def node_receivers(version: str):
        # REQ-F06: 本システムはReceiverを持たないため常に空配列
        _check_version(version, IS04_VERSIONS)
        return []

    # ---------------- Connection API (IS-05) ----------------

    @app.get("/x-nmos/connection/{version}/single/senders/{sender_id}/transportfile")
    def connection_transportfile(version: str, sender_id: str, db: Session = Depends(get_db)):
        _check_version(version, IS05_VERSIONS)
        scope = _scope_or_404(db)
        sender = find_sender_in_scope(scope, sender_id)
        if sender is None:
            raise HTTPException(status_code=404, detail="Sender not found in this AliasNode scope")
        return Response(content=sender.sdp_mirrored, media_type="application/sdp")

    @app.get("/x-nmos/connection/{version}/single/senders/{sender_id}/staged")
    def connection_staged_get(version: str, sender_id: str, db: Session = Depends(get_db)):
        _check_version(version, IS05_VERSIONS)
        return _connection_state(db, sender_id, staged=True)

    @app.patch("/x-nmos/connection/{version}/single/senders/{sender_id}/staged")
    async def connection_staged_patch(version: str, sender_id: str, request: Request, db: Session = Depends(get_db)):
        _check_version(version, IS05_VERSIONS)
        scope = _scope_or_404(db)
        sender = find_sender_in_scope(scope, sender_id)
        if sender is None:
            raise HTTPException(status_code=404, detail="Sender not found in this AliasNode scope")
        body = await request.json()
        key = f"{node_id}:{sender_id}"
        if "master_enable" in body:
            _active_state[key] = bool(body["master_enable"])
        activation = body.get("activation") or {}
        if activation.get("mode") == "activate_immediate":
            _active_state.setdefault(key, True)
        return _connection_state(db, sender_id, staged=True)

    @app.get("/x-nmos/connection/{version}/single/senders/{sender_id}/active")
    def connection_active_get(version: str, sender_id: str, db: Session = Depends(get_db)):
        _check_version(version, IS05_VERSIONS)
        return _connection_state(db, sender_id, staged=False)

    def _connection_state(db: Session, sender_id: str, staged: bool) -> dict:
        scope = _scope_or_404(db)
        sender = find_sender_in_scope(scope, sender_id)
        if sender is None:
            raise HTTPException(status_code=404, detail="Sender not found in this AliasNode scope")
        key = f"{node_id}:{sender_id}"
        master_enable = _active_state.get(key, sender.sync_status == "online")
        transport_params = parse_transport_params(sender.sdp_mirrored)
        return {
            "sender_id": sender_id,
            "master_enable": master_enable,
            "activation": {"mode": None, "requested_time": None, "activation_time": None},
            "transport_params": [transport_params],
        }

    return app
