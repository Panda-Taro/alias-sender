"""動作確認用の簡易シードデータ投入スクリプト。

実際のnmos-cpp RDSがない環境でもWebGUIの見た目・操作感を確認できるように、
ダミーのRealSenderと、AliasNode/AliasDevice/AliasConnector/AliasSenderの
一連の構成を作成する。

使い方:
    cd backend
    ALIAS_DB_PATH=data/alias_sender.db .venv/Scripts/python.exe scripts/seed_demo_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import models
from app.db.database import init_db, get_session
from app.services.alias_sender_logic import create_alias_sender

DEMO_SDP = {
    "video": "v=0\r\no=- 1 1 IN IP4 192.168.1.10\r\ns=FA1616 1-1\r\nc=IN IP4 239.1.1.1/32\r\nt=0 0\r\nm=video 5000 RTP/AVP 96\r\na=rtpmap:96 raw/90000\r\na=source-filter: incl IN IP4 239.1.1.1 192.168.1.10\r\n",
    "audio": "v=0\r\no=- 1 1 IN IP4 192.168.1.10\r\ns=FA1616 1-2\r\nc=IN IP4 239.1.1.2/32\r\nt=0 0\r\nm=audio 5010 RTP/AVP 97\r\na=rtpmap:97 L24/48000/2\r\na=source-filter: incl IN IP4 239.1.1.2 192.168.1.10\r\n",
    "ancillary": "v=0\r\no=- 1 1 IN IP4 192.168.1.10\r\ns=FA1616 1-3\r\nc=IN IP4 239.1.1.3/32\r\nt=0 0\r\nm=video 5020 RTP/AVP 98\r\na=rtpmap:98 smpte291/90000\r\na=source-filter: incl IN IP4 239.1.1.3 192.168.1.10\r\n",
}


def main() -> None:
    init_db()
    db = get_session()
    try:
        same_zone = db.query(models.SameZoneRdsConfig).first()
        if same_zone is None:
            same_zone = models.SameZoneRdsConfig(
                enabled=False, ip_address="192.168.1.10", port=80, query_api_version="v1.3"
            )
            db.add(same_zone)

        real_senders = {}
        for i, (media_type, sdp) in enumerate(DEMO_SDP.items(), start=1):
            rs = models.RealSender(
                nmos_node_id="demo-node-1",
                nmos_device_id="demo-device-1",
                nmos_sender_id=f"demo-sender-{i}",
                nmos_sender_label=f"FA1616 1-{i}",
                sdp_raw=sdp,
                media_type_detected=media_type,
                status="online",
            )
            db.add(rs)
            real_senders[media_type] = rs
        db.flush()

        node = models.AliasNode(
            alias_node_label="報道ゾーン",
            alias_node_description="デモ用Alias Node",
            node_api_enabled=True,
            node_api_port=10080,
        )
        db.add(node)
        db.flush()

        device = models.AliasDevice(alias_device_label="SB1", alias_device_description="キャリア")
        db.add(device)
        db.flush()

        db.add(models.NodeDeviceAssignment(node_id=node.id, device_id=device.id))
        db.flush()

        connector = models.AliasConnector(device_id=device.id, connector_label="SB1")
        db.add(connector)
        db.flush()

        for media_type, rs in real_senders.items():
            create_alias_sender(db, connector.id, rs.id, media_type, description=f"demo {media_type}")

        db.commit()
        print("Seed data created: 1 AliasNode / 1 AliasDevice / 1 AliasConnector / 3 AliasSenders")
    finally:
        db.close()


if __name__ == "__main__":
    main()
