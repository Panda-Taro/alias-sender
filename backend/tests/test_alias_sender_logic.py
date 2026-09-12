import pytest

from app.db import models
from app.services.alias_sender_logic import (
    AliasSenderError,
    build_label,
    create_alias_sender,
    propagate_sdp_update,
    set_real_sender_offline,
    set_real_sender_online,
    update_alias_sender_connector,
)


def _make_connector(db_session, label="SB1"):
    device = models.AliasDevice(alias_device_label="Carrier")
    db_session.add(device)
    db_session.flush()
    connector = models.AliasConnector(device_id=device.id, connector_label=label)
    db_session.add(connector)
    db_session.flush()
    return connector


def _make_real_sender(db_session, sdp="v=0\nm=video 5000 RTP/AVP 96\na=rtpmap:96 raw/90000\n"):
    real_sender = models.RealSender(
        nmos_node_id="node-1",
        nmos_device_id="device-1",
        nmos_sender_id="sender-1",
        nmos_sender_label="FA1616 1-1",
        sdp_raw=sdp,
        media_type_detected="video",
        status="online",
    )
    db_session.add(real_sender)
    db_session.flush()
    return real_sender


def test_build_label():
    assert build_label("SB1", "video") == "SB1_V"
    assert build_label("SB1", "audio") == "SB1_A"
    assert build_label("SB1", "ancillary") == "SB1_ANC"


def test_create_alias_sender_uses_real_sender_media_type_as_default(db_session):
    connector = _make_connector(db_session)
    real_sender = _make_real_sender(db_session)

    alias_sender = create_alias_sender(
        db_session, connector.id, real_sender.id, media_type=None, description="desc"
    )

    assert alias_sender.label == "SB1_V"
    assert alias_sender.media_type == "video"
    assert alias_sender.sdp_mirrored == real_sender.sdp_raw
    assert alias_sender.source_id is not None


def test_create_alias_sender_rejects_duplicate_media_type_in_connector(db_session):
    connector = _make_connector(db_session)
    real_sender = _make_real_sender(db_session)
    create_alias_sender(db_session, connector.id, real_sender.id, media_type="video", description="")

    with pytest.raises(AliasSenderError):
        create_alias_sender(db_session, connector.id, real_sender.id, media_type="video", description="")


def test_create_alias_sender_allows_up_to_three_distinct_media_types(db_session):
    connector = _make_connector(db_session)
    real_sender = _make_real_sender(db_session)

    create_alias_sender(db_session, connector.id, real_sender.id, media_type="video", description="")
    create_alias_sender(db_session, connector.id, real_sender.id, media_type="audio", description="")
    create_alias_sender(db_session, connector.id, real_sender.id, media_type="ancillary", description="")

    count = db_session.query(models.AliasSender).filter_by(connector_id=connector.id).count()
    assert count == 3


def test_update_alias_sender_connector_regenerates_label(db_session):
    connector_a = _make_connector(db_session, "SB1")
    connector_b = _make_connector(db_session, "KDDI1")
    real_sender = _make_real_sender(db_session)
    alias_sender = create_alias_sender(db_session, connector_a.id, real_sender.id, "video", "")

    update_alias_sender_connector(db_session, alias_sender, connector_b.id)

    assert alias_sender.connector_id == connector_b.id
    assert alias_sender.label == "KDDI1_V"


def test_propagate_sdp_update(db_session):
    connector = _make_connector(db_session)
    real_sender = _make_real_sender(db_session)
    alias_sender = create_alias_sender(db_session, connector.id, real_sender.id, "video", "")

    real_sender.sdp_raw = "v=0\nm=video 6000 RTP/AVP 96\na=rtpmap:96 raw/90000\n"
    propagate_sdp_update(db_session, real_sender)

    assert alias_sender.sdp_mirrored == real_sender.sdp_raw


def test_offline_then_online_cascades_to_alias_senders(db_session):
    connector = _make_connector(db_session)
    real_sender = _make_real_sender(db_session)
    alias_sender = create_alias_sender(db_session, connector.id, real_sender.id, "video", "")

    set_real_sender_offline(db_session, real_sender)
    assert real_sender.status == "offline"
    assert alias_sender.sync_status == "offline"

    new_sdp = "v=0\nm=video 7000 RTP/AVP 96\na=rtpmap:96 raw/90000\n"
    set_real_sender_online(db_session, real_sender, new_sdp)
    assert real_sender.status == "online"
    assert alias_sender.sync_status == "online"
    assert alias_sender.sdp_mirrored == new_sdp
