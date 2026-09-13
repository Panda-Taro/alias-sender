import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


MEDIA_TYPES = ("video", "audio", "ancillary")
ONLINE_OFFLINE = ("online", "offline")


class RealSender(Base):
    """同一ゾーンRDSから取得した本物のSender情報のローカルキャッシュ (⑩-1)"""

    __tablename__ = "real_senders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    nmos_node_id: Mapped[str] = mapped_column(String(36), nullable=False)
    nmos_device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    nmos_sender_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    nmos_sender_label: Mapped[str] = mapped_column(String(255), nullable=False)
    sdp_raw: Mapped[str] = mapped_column(Text, nullable=True, default="")
    media_type_detected: Mapped[str] = mapped_column(Enum(*MEDIA_TYPES, name="media_type_enum"), nullable=True)
    status: Mapped[str] = mapped_column(Enum(*ONLINE_OFFLINE, name="real_sender_status_enum"), default="online")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    alias_senders: Mapped[list["AliasSender"]] = relationship(back_populates="real_sender")


class AliasNode(Base):
    """本システム内の仮想Node (⑩-2)"""

    __tablename__ = "alias_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    alias_node_label: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_node_description: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    node_api_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    node_api_port: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    zone_rds_configs: Mapped[list["ZoneRdsConfig"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )
    device_assignments: Mapped[list["NodeDeviceAssignment"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class AliasDevice(Base):
    """AliasConnectorをまとめるグループ (⑩-3)"""

    __tablename__ = "alias_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    alias_device_label: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_device_description: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    connectors: Mapped[list["AliasConnector"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    node_assignments: Mapped[list["NodeDeviceAssignment"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class NodeDeviceAssignment(Base):
    """Node×DeviceのX-Yクロスポイント紐づけ (⑩-4)"""

    __tablename__ = "node_device_assignments"
    __table_args__ = (UniqueConstraint("node_id", "device_id", name="uq_node_device"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    node_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_nodes.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_devices.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    node: Mapped[AliasNode] = relationship(back_populates="device_assignments")
    device: Mapped[AliasDevice] = relationship(back_populates="node_assignments")


class AliasConnector(Base):
    """Device配下、V/A/ANC最大3つの束 (⑩-5)"""

    __tablename__ = "alias_connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_devices.id"), nullable=False)
    connector_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    device: Mapped[AliasDevice] = relationship(back_populates="connectors")
    senders: Mapped[list["AliasSender"]] = relationship(
        back_populates="connector", cascade="all, delete-orphan"
    )


class AliasSender(Base):
    """本システムの中核データ (⑩-6)"""

    __tablename__ = "alias_senders"
    __table_args__ = (
        UniqueConstraint("connector_id", "media_type", name="uq_connector_media_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    connector_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_connectors.id"), nullable=False)
    real_sender_id: Mapped[str] = mapped_column(String(36), ForeignKey("real_senders.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    media_type: Mapped[str] = mapped_column(Enum(*MEDIA_TYPES, name="alias_sender_media_type_enum"))
    sdp_mirrored: Mapped[str] = mapped_column(Text, nullable=True, default="")
    sync_status: Mapped[str] = mapped_column(Enum(*ONLINE_OFFLINE, name="alias_sender_sync_status_enum"), default="online")
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_id: Mapped[str] = mapped_column(String(36), default=gen_uuid)

    connector: Mapped[AliasConnector] = relationship(back_populates="senders")
    real_sender: Mapped[RealSender] = relationship(back_populates="alias_senders")
    registrations: Mapped[list["AliasSenderRegistration"]] = relationship(
        back_populates="alias_sender", cascade="all, delete-orphan"
    )

    @property
    def real_sender_label(self) -> str:
        """紐付け元Real Senderのラベル(WebGUI表示用, REQ-H03/H07)。"""
        return self.real_sender.nmos_sender_label if self.real_sender else ""


class AliasSenderRegistration(Base):
    """AliasSenderの他ゾーンRDS登録状態 (⑩-7)"""

    __tablename__ = "alias_sender_registrations"
    __table_args__ = (
        UniqueConstraint("alias_sender_id", "zone_rds_config_id", name="uq_sender_zone_rds"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    alias_sender_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_senders.id"), nullable=False)
    zone_rds_config_id: Mapped[str] = mapped_column(String(36), ForeignKey("zone_rds_configs.id"), nullable=False)
    registration_status: Mapped[str] = mapped_column(
        Enum(*ONLINE_OFFLINE, name="registration_status_enum"), default="offline"
    )
    last_registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    alias_sender: Mapped[AliasSender] = relationship(back_populates="registrations")
    zone_rds_config: Mapped["ZoneRdsConfig"] = relationship(back_populates="sender_registrations")


class SameZoneRdsConfig(Base):
    """同一ゾーンRDS接続設定 (⑩-8) - シングルトン想定"""

    __tablename__ = "same_zone_rds_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True, default="")
    port: Mapped[int] = mapped_column(Integer, nullable=True)
    query_api_version: Mapped[str] = mapped_column(String(16), nullable=True, default="v1.3")


class SystemSettings(Base):
    """本システム自体の設定 (WebGUI/管理APIの待受ポート等)。シングルトン想定。

    要件定義書⑩の9テーブルには存在しない、運用要望(WebGUIポート変更)に対応する
    ための追加テーブル。DECISIONS.md参照。
    """

    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    web_port: Mapped[int] = mapped_column(Integer, default=8000)


class ZoneRdsConfig(Base):
    """他ゾーンRDS接続設定 (⑩-9)

    registration_ip_address×registration_portの組にユニーク制約を課すことで、
    「1つのRDSに対して複数のAliasNodeを紐づけることは不可(排他制御)」(REQ-B03)を
    DBレベルで保証する。
    """

    __tablename__ = "zone_rds_configs"
    __table_args__ = (
        UniqueConstraint(
            "registration_ip_address", "registration_port", name="uq_zone_rds_ip_port"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    node_id: Mapped[str] = mapped_column(String(36), ForeignKey("alias_nodes.id"), nullable=False)
    registration_api_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_ip_address: Mapped[str] = mapped_column(String(64), nullable=True, default="")
    registration_port: Mapped[int] = mapped_column(Integer, nullable=True)
    registration_api_version: Mapped[str] = mapped_column(String(16), nullable=True, default="v1.3")

    node: Mapped[AliasNode] = relationship(back_populates="zone_rds_configs")
    sender_registrations: Mapped[list[AliasSenderRegistration]] = relationship(
        back_populates="zone_rds_config", cascade="all, delete-orphan"
    )
