"""Registration APIへの不要な再POSTが起きないことを確認する。

実運用で、他ゾーンRDS経由のNMOS Explorerのログに
「Added X」→「already maintained」が5秒おき(=ハートビート間隔)に
延々と繰り返される現象が観測された。実機の他Node(Xscend2)ではこの
繰り返しが発生しておらず、本システムが毎tickで内容不変のリソースを
無条件に再POSTしていたことが原因だった(通常のNMOS Nodeは変化時のみ
POST、それ以外はheartbeatのみを送る)。この回帰テストは、内容が
変化していない場合に2回目以降のtickでPOSTが送信されないことを保証する。
"""

from unittest.mock import AsyncMock

import pytest

from app.db import models
from app.services.alias_sender_logic import create_alias_sender
from app.services.registration_engine import RegistrationEngine


@pytest.fixture()
def scenario(db_session):
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

    zone_config = models.ZoneRdsConfig(
        node_id=node.id,
        registration_api_enabled=True,
        registration_ip_address="10.0.0.1",
        registration_port=3210,
        registration_api_version="v1.3",
    )
    db_session.add(zone_config)
    db_session.commit()

    return zone_config, alias_sender


@pytest.mark.asyncio
async def test_unchanged_resources_are_not_reposted_on_next_tick(db_session, scenario, monkeypatch):
    zone_config, _alias_sender = scenario

    register_mock = AsyncMock()
    heartbeat_mock = AsyncMock()
    monkeypatch.setattr("app.services.registration_client.NmosRegistrationClient.register_resource", register_mock)
    monkeypatch.setattr("app.services.registration_client.NmosRegistrationClient.heartbeat", heartbeat_mock)

    engine = RegistrationEngine()
    await engine._sync_one(db_session, zone_config)
    db_session.commit()
    first_tick_posts = register_mock.call_count
    assert first_tick_posts == 5  # node, device, source, flow, sender

    register_mock.reset_mock()
    await engine._sync_one(db_session, zone_config)
    db_session.commit()

    assert register_mock.call_count == 0
    assert heartbeat_mock.call_count == 2  # once per tick
