from app.db import models
from app.nmos import resources


def _make_alias_sender(media_type="video", sdp=None):
    if sdp is None:
        sdp = "v=0\nm=video 5000 RTP/AVP 96\na=rtpmap:96 raw/90000\na=fmtp:96 width=1280;height=720\n"
    return models.AliasSender(
        id="sender-1",
        connector_id="connector-1",
        real_sender_id="real-1",
        label="SB1_V",
        description="desc",
        media_type=media_type,
        sdp_mirrored=sdp,
        sync_status="online",
        source_id="source-1",
    )


def test_derive_flow_id_is_deterministic():
    a = resources.derive_flow_id("source-1")
    b = resources.derive_flow_id("source-1")
    c = resources.derive_flow_id("source-2")
    assert a == b
    assert a != c


def test_sender_resource_flow_id_matches_derived_flow_id():
    alias_sender = _make_alias_sender()
    sender_resource = resources.build_sender_resource(alias_sender, "device-1", "127.0.0.1", 10080, "v1.3")
    assert sender_resource["flow_id"] == resources.derive_flow_id(alias_sender.source_id)
    # flow_idはSource IDそのものであってはならない(旧実装の不具合の再発防止)
    assert sender_resource["flow_id"] != alias_sender.source_id


def test_flow_resource_uses_sdp_derived_dimensions():
    alias_sender = _make_alias_sender()
    flow = resources.build_flow_resource(alias_sender)
    assert flow["source_id"] == alias_sender.source_id
    assert flow["frame_width"] == 1280
    assert flow["frame_height"] == 720
    assert flow["media_type"] == "video/raw"


def test_flow_resource_falls_back_to_defaults_without_fmtp():
    alias_sender = _make_alias_sender(sdp="v=0\nm=video 5000 RTP/AVP 96\na=rtpmap:96 raw/90000\n")
    flow = resources.build_flow_resource(alias_sender)
    assert flow["frame_width"] == 1920
    assert flow["frame_height"] == 1080


def test_stable_version_unchanged_when_content_identical():
    alias_sender = _make_alias_sender()
    first = resources.build_sender_resource(alias_sender, "device-1", "127.0.0.1", 10080, "v1.3")
    second = resources.build_sender_resource(alias_sender, "device-1", "127.0.0.1", 10080, "v1.3")
    assert first["version"] == second["version"]


def test_stable_version_changes_when_content_changes():
    alias_sender = _make_alias_sender()
    before = resources.build_sender_resource(alias_sender, "device-1", "127.0.0.1", 10080, "v1.3")
    alias_sender.description = "changed"
    after = resources.build_sender_resource(alias_sender, "device-1", "127.0.0.1", 10080, "v1.3")
    assert before["version"] != after["version"]
