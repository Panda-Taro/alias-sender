from app.db import models
from app.services.alias_sender_logic import create_alias_sender
from app.services.scope import find_sender_in_scope, get_node_scope


def _setup_shared_device(db_session):
    node_a = models.AliasNode(alias_node_label="News Zone")
    node_b = models.AliasNode(alias_node_label="Production Zone")
    device = models.AliasDevice(alias_device_label="Carrier")
    db_session.add_all([node_a, node_b, device])
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

    alias_sender = create_alias_sender(db_session, connector.id, real_sender.id, "video", "")

    # AliasDevice「キャリア」を両方のAliasNodeに割り当てる (REQ-C03, AC-C01)
    db_session.add(models.NodeDeviceAssignment(node_id=node_a.id, device_id=device.id))
    db_session.add(models.NodeDeviceAssignment(node_id=node_b.id, device_id=device.id))
    db_session.flush()

    return node_a, node_b, device, alias_sender


def test_shared_device_visible_from_both_nodes(db_session):
    node_a, node_b, device, alias_sender = _setup_shared_device(db_session)

    scope_a = get_node_scope(db_session, node_a.id)
    scope_b = get_node_scope(db_session, node_b.id)

    assert [d.id for d in scope_a.devices] == [device.id]
    assert [d.id for d in scope_b.devices] == [device.id]
    assert find_sender_in_scope(scope_a, alias_sender.id) is not None
    assert find_sender_in_scope(scope_b, alias_sender.id) is not None


def test_node_without_assignment_has_empty_scope(db_session):
    lone_node = models.AliasNode(alias_node_label="Empty Zone")
    db_session.add(lone_node)
    db_session.flush()

    scope = get_node_scope(db_session, lone_node.id)
    assert scope.devices == []
    assert scope.senders == []


def test_sender_not_visible_outside_scope(db_session):
    node_a, node_b, device, alias_sender = _setup_shared_device(db_session)

    other_node = models.AliasNode(alias_node_label="Sports Zone")
    db_session.add(other_node)
    db_session.flush()

    scope_other = get_node_scope(db_session, other_node.id)
    assert find_sender_in_scope(scope_other, alias_sender.id) is None
