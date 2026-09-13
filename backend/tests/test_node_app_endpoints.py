"""Node APIの単体取得エンドポイント(REQ-F02/F03)の回帰テスト。

`GET /x-nmos/node/{version}/devices/{deviceId}`が実装されておらず404を返す
不具合が報告された。一覧(`/devices`)は正しくAliasNodeスコープでフィルタ
されているのに、単体取得ルート自体が存在しなかったことが原因。
"""

from fastapi.testclient import TestClient

from app.db import models
from app.db.database import get_db
from app.nmos.node_app import create_node_app
from app.services.alias_sender_logic import create_alias_sender


def _make_client(db_session, node_id: str) -> TestClient:
    app = create_node_app(node_id)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _build_scenario(db_session):
    node = models.AliasNode(alias_node_label="Sports", node_api_enabled=True, node_api_port=10099)
    device = models.AliasDevice(alias_device_label="Carrier")
    db_session.add_all([node, device])
    db_session.flush()
    db_session.add(models.NodeDeviceAssignment(node_id=node.id, device_id=device.id))
    db_session.flush()

    connector = models.AliasConnector(device_id=device.id, connector_label="SB1")
    db_session.add(connector)
    db_session.flush()

    real_sender = models.RealSender(
        nmos_node_id="n1",
        nmos_device_id="d1",
        nmos_sender_id="s1",
        nmos_sender_label="FA1616 1-1",
        sdp_raw="v=0\nm=video 5000 RTP/AVP 96\na=rtpmap:96 raw/90000\n",
        media_type_detected="video",
        status="online",
    )
    db_session.add(real_sender)
    db_session.flush()
    alias_sender = create_alias_sender(db_session, connector.id, real_sender.id, "video", "desc")
    db_session.commit()

    return node, device, alias_sender


def test_device_detail_returns_200_for_device_in_scope(db_session):
    node, device, _sender = _build_scenario(db_session)
    client = _make_client(db_session, node.id)

    response = client.get(f"/x-nmos/node/v1.3/devices/{device.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == device.id
    assert body["label"] == "Carrier"


def test_device_detail_matches_list_entry(db_session):
    node, device, _sender = _build_scenario(db_session)
    client = _make_client(db_session, node.id)

    list_response = client.get("/x-nmos/node/v1.3/devices")
    detail_response = client.get(f"/x-nmos/node/v1.3/devices/{device.id}")

    listed = next(d for d in list_response.json() if d["id"] == device.id)
    assert listed == detail_response.json()


def test_device_detail_advertises_connection_api_controls(db_session):
    node, device, _sender = _build_scenario(db_session)
    client = _make_client(db_session, node.id)

    response = client.get(f"/x-nmos/node/v1.3/devices/{device.id}")
    controls = response.json()["controls"]

    assert len(controls) >= 1
    hrefs = [c["href"] for c in controls]
    assert any(f":{node.node_api_port}/x-nmos/connection/" in href for href in hrefs)


def test_device_detail_404_for_unknown_id(db_session):
    node, _device, _sender = _build_scenario(db_session)
    client = _make_client(db_session, node.id)

    response = client.get("/x-nmos/node/v1.3/devices/00000000-0000-4000-8000-000000000000")

    assert response.status_code == 404


def test_device_detail_404_for_device_outside_scope(db_session):
    node, _device, _sender = _build_scenario(db_session)
    other_device = models.AliasDevice(alias_device_label="Not Assigned")
    db_session.add(other_device)
    db_session.commit()

    client = _make_client(db_session, node.id)
    response = client.get(f"/x-nmos/node/v1.3/devices/{other_device.id}")

    assert response.status_code == 404


def test_source_detail_still_works(db_session):
    """REQ-F03: /sources/{id}は既に実装済みであることの回帰確認。"""
    node, _device, sender = _build_scenario(db_session)
    client = _make_client(db_session, node.id)

    response = client.get(f"/x-nmos/node/v1.3/sources/{sender.source_id}")

    assert response.status_code == 200
    assert response.json()["id"] == sender.source_id
