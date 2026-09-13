"""生成したNode/Source/Flow/SenderリソースJSONを、実際のAMWA IS-04 v1.3
JSON schema(`tests/schemas/`に同梱)で検証する。

過去に`flow_core.json`が要求する`device_id`や`flow_video_raw.json`が要求する
`components`の欠落、`source_audio.json`のchannels[].symbolの不正なenum値
(RDS側の400 Bad Requestの原因)を、手作業のフィールドチェックだけでは検出でき
なかったため、実スキーマに対する検証をテストに組み込む。
"""

import json
from pathlib import Path

import jsonschema
import pytest

from app.db import models
from app.nmos import resources

SCHEMA_DIR = Path(__file__).parent / "schemas"


def _load_schema_store() -> dict[str, dict]:
    store = {}
    for path in SCHEMA_DIR.glob("*.json"):
        store[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return store


_STORE = _load_schema_store()


def _validate(schema_name: str, instance: dict) -> None:
    schema = _STORE[schema_name]
    resolver = jsonschema.RefResolver(base_uri="", referrer=schema, store=_STORE)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, resolver=resolver)
    errors = sorted(validator.iter_errors(instance), key=str)
    if errors:
        messages = "\n".join(f"- {e.json_path}: {e.message}" for e in errors)
        pytest.fail(f"{schema_name} validation failed for {instance.get('id')}:\n{messages}")


def _make_alias_sender(media_type: str, sdp: str) -> models.AliasSender:
    return models.AliasSender(
        id="11111111-1111-4111-8111-111111111111",
        connector_id="connector-1",
        real_sender_id="real-1",
        label="SB1",
        description="desc",
        media_type=media_type,
        sdp_mirrored=sdp,
        sync_status="online",
        source_id="22222222-2222-4222-8222-222222222222",
    )


VIDEO_SDP = "v=0\nm=video 5000 RTP/AVP 96\na=rtpmap:96 raw/90000\na=fmtp:96 width=1920;height=1080\n"
AUDIO_SDP = "v=0\nm=audio 5010 RTP/AVP 97\na=rtpmap:97 L24/48000/2\n"
ANC_SDP = "v=0\nm=video 5020 RTP/AVP 98\na=rtpmap:98 smpte291/90000\n"

DEVICE_ID = "33333333-3333-4333-8333-333333333333"


@pytest.mark.parametrize(
    ("media_type", "sdp", "source_schema"),
    [
        ("video", VIDEO_SDP, "source_generic.json"),
        ("audio", AUDIO_SDP, "source_audio.json"),
        ("ancillary", ANC_SDP, "source_data.json"),
    ],
)
def test_source_resource_matches_schema(media_type, sdp, source_schema):
    alias_sender = _make_alias_sender(media_type, sdp)
    source = resources.build_source_resource(alias_sender, DEVICE_ID)
    _validate(source_schema, source)


@pytest.mark.parametrize(
    ("media_type", "sdp", "flow_schema"),
    [
        ("video", VIDEO_SDP, "flow_video_raw.json"),
        ("audio", AUDIO_SDP, "flow_audio_raw.json"),
        ("ancillary", ANC_SDP, "flow_sdianc_data.json"),
    ],
)
def test_flow_resource_matches_schema(media_type, sdp, flow_schema):
    alias_sender = _make_alias_sender(media_type, sdp)
    flow = resources.build_flow_resource(alias_sender, DEVICE_ID)
    _validate(flow_schema, flow)


@pytest.mark.parametrize("media_type,sdp", [("video", VIDEO_SDP), ("audio", AUDIO_SDP), ("ancillary", ANC_SDP)])
def test_sender_resource_matches_schema(media_type, sdp):
    alias_sender = _make_alias_sender(media_type, sdp)
    sender = resources.build_sender_resource(alias_sender, DEVICE_ID, "127.0.0.1", 10080, "v1.3")
    _validate("sender.json", sender)


def test_node_resource_matches_schema():
    node = models.AliasNode(
        id="44444444-4444-4444-8444-444444444444",
        alias_node_label="News Zone",
        alias_node_description="desc",
        node_api_enabled=True,
        node_api_port=10080,
    )
    node_resource = resources.build_node_resource(node, "127.0.0.1", 10080)
    # nodeの完全なスキーマ(services/clocks/interfaces等)は未取得のため、
    # 共通のresource_core部分のみ検証する。
    _validate("resource_core.json", node_resource)


def test_device_resource_matches_schema_and_advertises_connection_api():
    device = models.AliasDevice(
        id="55555555-5555-4555-8555-555555555555",
        alias_device_label="Carrier",
        alias_device_description="desc",
    )
    device_resource = resources.build_device_resource(
        device, "44444444-4444-4444-8444-444444444444", [], "127.0.0.1", 10080
    )
    _validate("device.json", device_resource)

    # REQ-F02: controlsにIS-05 Connection APIのhrefが含まれていること
    # (デバイス単体取得が404のままだとNMOSコントローラーがこのhrefへ
    # 到達できず、Connection API接続に失敗する)
    control_types = {c["type"] for c in device_resource["controls"]}
    assert "urn:x-nmos:control:sr-ctrl/v1.0" in control_types
    assert "urn:x-nmos:control:sr-ctrl/v1.1" in control_types
    for control in device_resource["controls"]:
        assert control["href"].startswith("http://127.0.0.1:10080/x-nmos/connection/")
