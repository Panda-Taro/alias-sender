"""AliasNode/AliasDevice/AliasSource/AliasSenderをNMOS IS-04リソースJSONへ
変換するビルダー群。Node API(自己記述)とRegistration API(他ゾーンRDSへの登録)の
両方から共有される。

NMOSリソースの`version`フィールドはTAI風のタイムスタンプ文字列
("<seconds>:<nanoseconds>")とする(簡易実装。UTC秒を代用しTAIオフセットは
考慮しない)。
"""

import time

from app.db import models

FORMAT_MAP = {
    "video": "urn:x-nmos:format:video",
    "audio": "urn:x-nmos:format:audio",
    "ancillary": "urn:x-nmos:format:data",
}

NMOS_API_VERSIONS = ["v1.0", "v1.1", "v1.2", "v1.3"]


def nmos_version_now() -> str:
    now = time.time()
    seconds = int(now)
    nanoseconds = int((now - seconds) * 1e9)
    return f"{seconds}:{nanoseconds}"


def build_node_resource(node: models.AliasNode, host: str, port: int) -> dict:
    return {
        "id": node.id,
        "version": nmos_version_now(),
        "label": node.alias_node_label,
        "description": node.alias_node_description or "",
        "tags": {},
        "href": f"http://{host}:{port}/",
        "hostname": host,
        "api": {
            "versions": NMOS_API_VERSIONS,
            "endpoints": [
                {"host": host, "port": port, "protocol": "http"},
            ],
        },
        "caps": {},
        "services": [],
        "clocks": [],
        "interfaces": [],
    }


def build_device_resource(device: models.AliasDevice, node_id: str, sender_ids: list[str]) -> dict:
    return {
        "id": device.id,
        "version": nmos_version_now(),
        "label": device.alias_device_label,
        "description": device.alias_device_description or "",
        "tags": {},
        "type": "urn:x-nmos:device:generic",
        "node_id": node_id,
        "senders": sender_ids,
        "receivers": [],
        "controls": [],
    }


def build_source_resource(alias_sender: models.AliasSender, device_id: str) -> dict:
    resource = {
        "id": alias_sender.source_id,
        "version": nmos_version_now(),
        "label": alias_sender.label,
        "description": alias_sender.description or "",
        "tags": {},
        "format": FORMAT_MAP[alias_sender.media_type],
        "caps": {},
        "device_id": device_id,
        "parents": [],
        "clock_name": None,
    }
    if alias_sender.media_type == "audio":
        resource["channels"] = [{"label": "ch1", "symbol": "M"}]
    return resource


def build_sender_resource(
    alias_sender: models.AliasSender, device_id: str, host: str, port: int, version: str
) -> dict:
    return {
        "id": alias_sender.id,
        "version": nmos_version_now(),
        "label": alias_sender.label,
        "description": alias_sender.description or "",
        "tags": {},
        # 本システムはFlowリソースを独自に生成しない(⑪6)ため、source_idを暫定的にflow_idへ流用する
        "flow_id": alias_sender.source_id,
        "transport": "urn:x-nmos:transport:rtp.mcast",
        "device_id": device_id,
        "manifest_href": f"http://{host}:{port}/x-nmos/node/{version}/senders/{alias_sender.id}/transportfile",
        "interface_bindings": [],
        "subscription": {"receiver_id": None, "active": alias_sender.sync_status == "online"},
    }
