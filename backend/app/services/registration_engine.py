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
        # tracks the last successfully-sent `version` per (zone_rds_config_id, "type:id"),
        # so unchanged resources are not re-POSTed every tick (see _register_if_changed).
        self._last_sent_version: dict[str, dict[str, str]] = {}

    async def _register_if_changed(
        self, client: NmosRegistrationClient, config_id: str, resource_type: str, data: dict
    ) -> None:
        """内容が前回送信時と同一であれば再POSTしない。

        従来は毎tick(5秒ごと)、内容が変化していなくてもnode/device/source/
        flow/senderを無条件で再POSTしていた。実運用で他ゾーンRDS
        (nmos-cpp)経由のNMOS Explorerのログを見ると、本システムのリソースに
        ついてのみ5秒おきに"Added"通知が繰り返し発生しており、実機の他Node
        (Xscend2)ではこの繰り返しが発生していなかった。これはNMOSの通常の
        Node実装が「変化時のみPOST、それ以外は/healthハートビートのみ」という
        作法に沿っていないことを示しており、クライアント側の不要な再処理
        (今回の"Cannot connect"と直接関係するかは未確定だが、プロトコル上の
        振る舞いの差異として明確な不具合)の原因になっていた。
        """
        versions = self._last_sent_version.setdefault(config_id, {})
        key = f"{resource_type}:{data['id']}"
        if versions.get(key) == data.get("version"):
            return
        await client.register_resource(resource_type, data)
        versions[key] = data.get("version")

    def _forget_sent_version(self, config_id: str, resource_type: str, resource_id: str) -> None:
        self._last_sent_version.get(config_id, {}).pop(f"{resource_type}:{resource_id}", None)

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
            config.registration_ip_address,
            config.registration_port,
            config.registration_api_version,
            source_port=config.registration_source_port,
        )
        host = get_primary_ip()
        port = scope.node.node_api_port or settings.node_api_port_start
        version = config.registration_api_version

        errors: list[str] = []

        # ---- Node登録 (これが失敗した場合はDevice/Sender登録・ハートビートも
        #      成立しないため、ここだけは失敗したら即座に終了する) ----
        try:
            node_resource = resources.build_node_resource(scope.node, host, port)
            await self._register_if_changed(client, config.id, "node", node_resource)
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
                device_resource = resources.build_device_resource(
                    device, config.node_id, device_sender_ids.get(device.id, []), host, port
                )
                await self._register_if_changed(client, config.id, "device", device_resource)
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

                if alias_sender.sync_status != "online":
                    if alias_sender.id in currently_registered:
                        for rtype, rid in (
                            ("sender", alias_sender.id),
                            ("flow", resources.derive_flow_id(alias_sender.source_id)),
                            ("source", alias_sender.source_id),
                        ):
                            try:
                                await client.delete_resource(rtype, rid)
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "Deregistration failed (zone RDS %s, %s %s): %s", config.id, rtype, rid, exc
                                )
                            self._forget_sent_version(config.id, rtype, rid)
                        currently_registered.discard(alias_sender.id)
                    reg.registration_status = "offline"
                    senders_ok += 1  # 意図的にoffline: エラーではない
                    continue

                # source/flow/sourceは互いに参照するため、1つでも失敗すれば
                # このAliasSenderはonline扱いにしないが、どの資源で失敗した
                # かを個別に記録できるよう例外を分離する(2件目以降の呼び出しは
                # 前段が失敗していても診断のためにあえて試行する)。
                sender_errors: list[str] = []
                try:
                    source_resource = resources.build_source_resource(alias_sender, connector.device_id)
                    await self._register_if_changed(client, config.id, "source", source_resource)
                except Exception as exc:  # noqa: BLE001
                    sender_errors.append(f"source registration failed: {exc}")

                try:
                    flow_resource = resources.build_flow_resource(alias_sender, connector.device_id)
                    await self._register_if_changed(client, config.id, "flow", flow_resource)
                except Exception as exc:  # noqa: BLE001
                    sender_errors.append(f"flow registration failed: {exc}")

                try:
                    sender_resource = resources.build_sender_resource(
                        alias_sender, connector.device_id, host, port, version
                    )
                    await self._register_if_changed(client, config.id, "sender", sender_resource)
                except Exception as exc:  # noqa: BLE001
                    sender_errors.append(f"sender registration failed: {exc}")

                if sender_errors:
                    reg.registration_status = "offline"
                    message = f"{alias_sender.label}: " + " / ".join(sender_errors)
                    errors.append(message)
                    logger.warning("Sender registration failed (zone RDS %s): %s", config.id, message)
                else:
                    reg.registration_status = "online"
                    reg.last_registered_at = datetime.now(timezone.utc)
                    currently_registered.add(alias_sender.id)
                    senders_ok += 1

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

            # ハートビートの失敗(特に404)は、RDS側が再起動等で当該Nodeの登録を
            # 失った/知らないことを意味する。このまま_register_if_changed()の
            # キャッシュを保持し続けると、内容が変わらない限り二度と
            # POST /resourceを再送しないため、無限に404を繰り返して復旧
            # しなくなってしまう(実運用で確認された不具合)。キャッシュを
            # 破棄し、次のtickでnode/device/source/flow/senderを無条件に
            # 再POSTして自己修復させる。
            self._last_sent_version.pop(config.id, None)
            self._registered_sender_ids.pop(config.id, None)

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
