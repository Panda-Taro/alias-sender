from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MediaType = Literal["video", "audio", "ancillary"]
OnlineOffline = Literal["online", "offline"]


# ---------- RealSender ----------


class RealSenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nmos_node_id: str
    nmos_device_id: str
    nmos_sender_id: str
    nmos_sender_label: str
    media_type_detected: Optional[MediaType]
    status: OnlineOffline
    last_seen_at: datetime


class RealSenderDetailOut(RealSenderOut):
    sdp_raw: str


# ---------- SameZoneRdsConfig ----------


class SameZoneRdsConfigIn(BaseModel):
    enabled: bool = False
    ip_address: str = ""
    port: Optional[int] = None
    query_api_version: str = "v1.3"


class SameZoneRdsConfigOut(SameZoneRdsConfigIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    connection_status: OnlineOffline = "offline"


# ---------- AliasNode ----------


class AliasNodeIn(BaseModel):
    alias_node_label: str
    alias_node_description: str = ""
    node_api_enabled: bool = False
    node_api_port: Optional[int] = None


class AliasNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alias_node_label: str
    alias_node_description: str
    node_api_enabled: bool
    node_api_port: Optional[int]
    created_at: datetime


# ---------- ZoneRdsConfig ----------


class ZoneRdsConfigIn(BaseModel):
    node_id: str
    registration_api_enabled: bool = False
    registration_ip_address: str
    registration_port: int
    registration_api_version: str = "v1.3"


class ZoneRdsConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node_id: str
    registration_api_enabled: bool
    registration_ip_address: str
    registration_port: int
    registration_api_version: str
    connection_status: OnlineOffline = "offline"


# ---------- AliasDevice ----------


class AliasDeviceIn(BaseModel):
    alias_device_label: str
    alias_device_description: str = ""


class AliasDeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alias_device_label: str
    alias_device_description: str
    created_at: datetime


class NodeDeviceAssignmentIn(BaseModel):
    node_id: str
    device_id: str


class NodeDeviceAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node_id: str
    device_id: str
    assigned_at: datetime


# ---------- AliasConnector ----------


class AliasConnectorIn(BaseModel):
    device_id: str
    connector_label: str


class AliasConnectorUpdateIn(BaseModel):
    connector_label: str


class AliasConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    connector_label: str
    created_at: datetime


# ---------- AliasSender ----------


class AliasSenderCreateIn(BaseModel):
    connector_id: str
    real_sender_id: str
    media_type: Optional[MediaType] = None
    description: str = ""


class AliasSenderUpdateIn(BaseModel):
    connector_id: Optional[str] = None
    description: Optional[str] = None
    media_type: Optional[MediaType] = None


class AliasSenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_id: str
    real_sender_id: str
    label: str
    description: str
    media_type: MediaType
    sync_status: OnlineOffline
    last_synced_at: datetime
    source_id: str


class AliasSenderDetailOut(AliasSenderOut):
    sdp_mirrored: str


# ---------- Dashboard / composite views ----------


class ConnectorWithSenders(BaseModel):
    id: str
    connector_label: str
    senders: list[AliasSenderOut]


class DeviceWithConnectors(BaseModel):
    id: str
    alias_device_label: str
    alias_device_description: str
    connectors: list[ConnectorWithSenders]


class NodeTreeOut(BaseModel):
    node: AliasNodeOut
    devices: list[DeviceWithConnectors]
    zone_rds_configs: list[ZoneRdsConfigOut]


class SystemInfoOut(BaseModel):
    os_ip_addresses: list[str]
    web_port: int
    node_api_port_start: int


class WebPortIn(BaseModel):
    web_port: int = Field(ge=1, le=65535)
