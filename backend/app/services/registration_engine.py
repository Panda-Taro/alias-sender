"""他ゾーンRDSへの登録・ハートビートエンジン (REQ-E01〜E06, ⑦④, ⑪4-③)。

AliasNode単位でZoneRdsConfigごとに以下を行う:
  - スコープ内(NodeDeviceAssignment経由)のDevice/Connector/Sender/Sourceを
    node/device/source/senderリソースとして登録する
  - AliasSender.sync_statusがonlineのものだけを有効な登録として維持し、
    offlineになったものはDELETEで登録解除する(REQ-E04/E05)
  - 5秒間隔でハートビートを送信し続ける(REQ-E03)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import settings
from app.db import models
from app.db.database import get_session
from app.nmos import resources
from app.services.host_info import get_primary_ip
from app.services.registration_client import NmosRegistrationClient
from app.services.scope import get_node_scope

logger = logging.getLogger(__name__)


@dataclass
class ZoneRdsStatus:
    connected: bool = False
    last_error: str | None = None
    last_registered_at: datetime | None = None
    senders_ok: int = 0
    senders_total: int = 0


# key: zone_rds_config_id
zone_status: dict[str, ZoneRdsStatus] = {}


class RegistrationEngine:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = False
        # tracks which resource ids are currently believed registered per zone_rds_config_id
        self._registered_sender_ids: dict[str, set[str]] = {}

    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
        self._task = None

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                logger.exception("registration engine tick failed")
            await asyncio.sleep(settings.heartbeat_interval_seconds)

    async def _tick(self) -> None:
        db = get_session()
        try:
            configs = (
                db.query(models.ZoneRdsConfig)
                .filter(models.ZoneRdsConfig.registration_api_enabled.is_(True))
                .all()
            )
            for config in configs:
                await self._sync_one(db, config)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _sync_one(self, db, config: models.ZoneRdsConfig) -> None:
        """他ゾーンRDSへの登録を行う。

        1つのSender/Deviceの登録に失敗しても、他のリソースの登録や末尾の
        ハートビート送信を中断しない(REQ-E03)。以前はsource/sender登録の
        例外がハートビート送信自体を丸ごとスキップさせてしまい、RDS側の
        ヘルスチェックタイムアウトでAliasNodeが定期的に消失する不具合が
        あったため、リソース種別ごとに例外を握って継続する構成にしている。
        """
        st = zone_status.setdefault(config.id, ZoneRdsStatus())
        scope = get_node_scope(db, config.node_id)
        if scope is None:
            return

        client = NmosRegistrationClient(
            config.registration_ip_address, config.registration_port, config.registration_api_version
        )
        host = get_primary_ip()
        port = scope.node.node_api_port or settings.node_api_port_start
        version = config.registration_api_version

        errors: list[str] = []

        # ---- Node登録 (これが失敗した場合はDevice/Sender登録・ハートビートも
        #      成立しないため、ここだけは失敗したら即座に終了する) ----
        try:
            node_resource = resources.build_node_resource(scope.node, host, port)
            await client.register_resource("node", node_resource)
        except Exception as exc:  # noqa: BLE001
            st.connected = False
            st.last_error = f"node registration failed: {exc}"
            logger.warning("Node registration failed for zone RDS %s: %s", config.id, exc)
            return

        # ---- Device登録 (1台失敗しても他のDeviceの登録・後続処理は続行) ----
        device_sender_ids: dict[str, list[str]] = {d.id: [] for d in scope.devices}
        for connector in scope.connectors:
            for s in connector.senders:
                device_sender_ids.setdefault(connector.device_id, []).append(s.id)

        for device in scope.devices:
            try:
                await client.register_resource(
                    "device",
                    resources.build_device_resource(device, config.node_id, device_sender_ids.get(device.id, [])),
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"device {device.alias_device_label} registration failed: {exc}")
                logger.warning("Device registration failed (zone RDS %s, device %s): %s", config.id, device.id, exc)

        # ---- Source/Flow/Sender登録 (1つのSenderの失敗が他のSenderや
        #      ハートビートに影響しないようにする) ----
        currently_registered = self._registered_sender_ids.setdefault(config.id, set())
        senders_total = 0
        senders_ok = 0
        for connector in scope.connectors:
            for alias_sender in connector.senders:
                senders_total += 1
                reg = self._get_or_create_registration(db, alias_sender.id, config.id)
                try:
                    if alias_sender.sync_status == "online":
                        await client.register_resource(
                            "source", resources.build_source_resource(alias_sender, connector.device_id)
                        )
                        await client.register_resource("flow", resources.build_flow_resource(alias_sender))
                        await client.register_resource(
                            "sender",
                            resources.build_sender_resource(alias_sender, connector.device_id, host, port, version),
                        )
                        reg.registration_status = "online"
                        reg.last_registered_at = datetime.now(timezone.utc)
                        currently_registered.add(alias_sender.id)
                        senders_ok += 1
                    else:
                        if alias_sender.id in currently_registered:
                            await client.delete_resource("sender", alias_sender.id)
                            await client.delete_resource("flow", resources.derive_flow_id(alias_sender.source_id))
                            await client.delete_resource("source", alias_sender.source_id)
                            currently_registered.discard(alias_sender.id)
                        reg.registration_status = "offline"
                        senders_ok += 1  # 意図的にoffline: エラーではない
                except Exception as exc:  # noqa: BLE001
                    reg.registration_status = "offline"
                    errors.append(f"sender {alias_sender.label} registration failed: {exc}")
                    logger.warning(
                        "Sender registration failed (zone RDS %s, sender %s): %s", config.id, alias_sender.id, exc
                    )

        st.senders_total = senders_total
        st.senders_ok = senders_ok

        # ---- ハートビート (Node/Deviceの一部失敗があっても必ず送信を試みる) ----
        try:
            await client.heartbeat(config.node_id)
            st.connected = True
            st.last_registered_at = datetime.now(timezone.utc)
            st.last_error = "; ".join(errors) if errors else None
        except Exception as exc:  # noqa: BLE001
            st.connected = False
            errors.append(f"heartbeat failed: {exc}")
            st.last_error = "; ".join(errors)
            logger.warning("Heartbeat failed for zone RDS %s: %s", config.id, exc)

    @staticmethod
    def _get_or_create_registration(db, alias_sender_id: str, zone_rds_config_id: str) -> models.AliasSenderRegistration:
        reg = (
            db.query(models.AliasSenderRegistration)
            .filter(
                models.AliasSenderRegistration.alias_sender_id == alias_sender_id,
                models.AliasSenderRegistration.zone_rds_config_id == zone_rds_config_id,
            )
            .first()
        )
        if reg is None:
            reg = models.AliasSenderRegistration(
                alias_sender_id=alias_sender_id,
                zone_rds_config_id=zone_rds_config_id,
                registration_status="offline",
            )
            db.add(reg)
            db.flush()
        return reg


engine = RegistrationEngine()
