"""AliasNode/AliasDevice/AliasSource/AliasFlow/AliasSenderをNMOS IS-04
リソースJSONへ変換するビルダー群。Node API(自己記述)とRegistration API
(他ゾーンRDSへの登録)の両方から共有される。

NMOSリソースの`version`フィールドはTAI風のタイムスタンプ文字列
("<seconds>:<nanoseconds>")とする(簡易実装。UTC秒を代用しTAIオフセットは
考慮しない)。IS-04の作法では`version`はリソースの内容が実際に変化した時のみ
更新するべきであり、毎回変えると受信側(RDS/コントローラー)に不要な
MODIFIED通知を発生させ続け、表示のちらつきの原因になる。そのため、
内容のハッシュが前回と同じ場合は同じversion文字列を再利用する
(`_stable_version`, DECISIONS.md参照)。
"""

import hashlib
import json
import time
import uuid

from app.db import models

FORMAT_MAP = {
    "video": "urn:x-nmos:format:video",
    "audio": "urn:x-nmos:format:audio",
    "ancillary": "urn:x-nmos:format:data",
}

NMOS_API_VERSIONS = ["v1.0", "v1.1", "v1.2", "v1.3"]

_version_cache: dict[str, tuple[str, str]] = {}


def nmos_version_now() -> str:
    now = time.time()
    seconds = int(now)
    nanoseconds = int((now - seconds) * 1e9)
    return f"{seconds}:{nanoseconds}"


def _stable_version(resource_id: str, content: dict) -> str:
    content_hash = hashlib.sha1(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
    cached = _version_cache.get(resource_id)
    if cached and cached[0] == content_hash:
        return cached[1]
    version = nmos_version_now()
    _version_cache[resource_id] = (content_hash, version)
    return version


def derive_flow_id(source_id: str) -> str:
    """本システムはSourceと1:1のFlowを都度生成しないため、source_idから
    決定的に導出した固定UUIDをflow_idとして使用する(⑪6, DECISIONS.md参照)。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:alias-sender:flow:{source_id}"))


def build_node_resource(node: models.AliasNode, host: str, port: int) -> dict:
    content = {
        "label": node.alias_node_label,
        "description": node.alias_node_description or "",
        "href": f"http://{host}:{port}/",
        "hostname": host,
        "endpoints": [{"host": host, "port": port, "protocol": "http"}],
    }
    return {
        "id": node.id,
        "version": _stable_version(f"node:{node.id}", content),
        "label": content["label"],
        "description": content["description"],
        "tags": {},
        "href": content["href"],
        "hostname": content["hostname"],
        "api": {
            "versions": NMOS_API_VERSIONS,
            "endpoints": content["endpoints"],
        },
        "caps": {},
        "services": [],
        "clocks": [],
        "interfaces": [],
    }


def build_device_resource(device: models.AliasDevice, node_id: str, sender_ids: list[str]) -> dict:
    content = {
        "label": device.alias_device_label,
        "description": device.alias_device_description or "",
        "node_id": node_id,
        "senders": sorted(sender_ids),
    }
    return {
        "id": device.id,
        "version": _stable_version(f"device:{device.id}:{node_id}", content),
        "label": content["label"],
        "description": content["description"],
        "tags": {},
        "type": "urn:x-nmos:device:generic",
        "node_id": node_id,
        "senders": sender_ids,
        "receivers": [],
        "controls": [],
    }


def build_source_resource(alias_sender: models.AliasSender, device_id: str) -> dict:
    content = {
        "label": alias_sender.label,
        "description": alias_sender.description or "",
        "format": FORMAT_MAP[alias_sender.media_type],
        "device_id": device_id,
    }
    resource = {
        "id": alias_sender.source_id,
        "version": _stable_version(f"source:{alias_sender.source_id}", content),
        "label": content["label"],
        "description": content["description"],
        "tags": {},
        "format": content["format"],
        "caps": {},
        "device_id": device_id,
        "parents": [],
        "clock_name": None,
    }
    if alias_sender.media_type == "audio":
        resource["channels"] = [{"label": "ch1", "symbol": "M"}]
    return resource


def build_flow_resource(alias_sender: models.AliasSender) -> dict:
    """AliasSenderに対応する最小限のFlowリソースを生成する(⑪6)。

    本システムは実際の映像音声アンシラリを生成/解析しないため、SDPの
    fmtp/rtpmapから技術パラメータを推定できる範囲で反映し、判定できない
    項目は一般的な放送用途の既定値にフォールバックする(近似実装、
    DECISIONS.md参照)。
    """
    from app.services.sdp_utils import parse_flow_technical_params

    flow_id = derive_flow_id(alias_sender.source_id)
    params = parse_flow_technical_params(alias_sender.sdp_mirrored)

    flow = {
        "id": flow_id,
        "label": alias_sender.label,
        "description": alias_sender.description or "",
        "tags": {},
        "source_id": alias_sender.source_id,
        "parents": [],
        "format": FORMAT_MAP[alias_sender.media_type],
    }

    if alias_sender.media_type == "video":
        flow["frame_width"] = int(params.get("width", 1920))
        flow["frame_height"] = int(params.get("height", 1080))
        flow["interlace_mode"] = "progressive"
        flow["colorspace"] = params.get("colorimetry", "BT709")
        flow["media_type"] = "video/raw"
    elif alias_sender.media_type == "audio":
        encoding = params.get("encoding", "l24")
        bit_depth = {"l16": 16, "l24": 24, "l32": 32}.get(encoding, 24)
        flow["media_type"] = f"audio/L{bit_depth}"
        flow["bit_depth"] = bit_depth
        flow["sample_rate"] = {"numerator": int(params.get("clock_rate", 48000)), "denominator": 1}
    else:
        flow["media_type"] = "video/smpte291"

    flow["version"] = _stable_version(f"flow:{flow_id}", {k: v for k, v in flow.items() if k != "id"})
    return flow


def build_sender_resource(
    alias_sender: models.AliasSender, device_id: str, host: str, port: int, version: str
) -> dict:
    content = {
        "label": alias_sender.label,
        "description": alias_sender.description or "",
        "flow_id": derive_flow_id(alias_sender.source_id),
        "device_id": device_id,
        "active": alias_sender.sync_status == "online",
    }
    return {
        "id": alias_sender.id,
        "version": _stable_version(f"sender:{alias_sender.id}", content),
        "label": content["label"],
        "description": content["description"],
        "tags": {},
        "flow_id": content["flow_id"],
        "transport": "urn:x-nmos:transport:rtp.mcast",
        "device_id": device_id,
        "manifest_href": f"http://{host}:{port}/x-nmos/node/{version}/senders/{alias_sender.id}/transportfile",
        "interface_bindings": [],
        "subscription": {"receiver_id": None, "active": content["active"]},
    }
