const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type MediaType = "video" | "audio" | "ancillary";
export type OnlineOffline = "online" | "offline";

export interface RealSender {
  id: string;
  nmos_node_id: string;
  nmos_device_id: string;
  nmos_sender_id: string;
  nmos_sender_label: string;
  media_type_detected: MediaType | null;
  status: OnlineOffline;
  last_seen_at: string;
}

export interface RealSenderDetail extends RealSender {
  sdp_raw: string;
}

export interface SameZoneRdsConfig {
  id: string;
  enabled: boolean;
  ip_address: string;
  port: number | null;
  query_api_version: string;
  connection_status: OnlineOffline;
}

export interface ZoneRdsConfig {
  id: string;
  node_id: string;
  registration_api_enabled: boolean;
  registration_ip_address: string;
  registration_port: number;
  registration_api_version: string;
  registration_source_port: number | null;
  connection_status: OnlineOffline;
}

export interface AliasNode {
  id: string;
  alias_node_label: string;
  alias_node_description: string;
  node_api_enabled: boolean;
  node_api_port: number | null;
  created_at: string;
}

export interface AliasDevice {
  id: string;
  alias_device_label: string;
  alias_device_description: string;
  created_at: string;
}

export interface NodeDeviceAssignment {
  id: string;
  node_id: string;
  device_id: string;
  assigned_at: string;
}

export interface AliasConnector {
  id: string;
  device_id: string;
  connector_label: string;
  created_at: string;
}

export interface AliasSender {
  id: string;
  connector_id: string;
  real_sender_id: string;
  real_sender_label: string;
  label: string;
  description: string;
  media_type: MediaType;
  sync_status: OnlineOffline;
  last_synced_at: string;
  source_id: string;
}

export interface AliasSenderDetail extends AliasSender {
  sdp_mirrored: string;
}

export interface ConnectorWithSenders {
  id: string;
  connector_label: string;
  senders: AliasSender[];
}

export interface DeviceWithConnectors {
  id: string;
  alias_device_label: string;
  alias_device_description: string;
  connectors: ConnectorWithSenders[];
}

export interface NodeTree {
  node: AliasNode;
  devices: DeviceWithConnectors[];
  zone_rds_configs: ZoneRdsConfig[];
}

export interface SystemInfo {
  os_ip_addresses: string[];
  web_port: number;
  node_api_port_start: number;
}

export interface RdsStatus {
  same_zone: {
    enabled: boolean;
    ip_address: string;
    port: number | null;
    query_api_version: string;
    connected: boolean;
    ws_connected: boolean;
    last_error: string | null;
  };
  other_zones: Array<{
    id: string;
    node_id: string;
    ip_address: string;
    port: number;
    registration_api_version: string;
    enabled: boolean;
    connected: boolean;
    last_error: string | null;
    senders_ok: number;
    senders_total: number;
  }>;
}

export interface SameZoneTreeNode {
  nmos_node_id: string;
  devices: Array<{
    nmos_device_id: string;
    senders: RealSender[];
    receivers: unknown[];
  }>;
}

export const api = {
  // dashboard
  rdsStatus: () => request<RdsStatus>("/dashboard/rds-status"),
  sameZoneTree: () => request<SameZoneTreeNode[]>("/dashboard/same-zone-tree"),
  aliasNodeTree: () => request<NodeTree[]>("/dashboard/alias-node-tree"),

  // same-zone / zone rds config
  getSameZoneRds: () => request<SameZoneRdsConfig>("/same-zone-rds"),
  putSameZoneRds: (body: Omit<SameZoneRdsConfig, "id" | "connection_status">) =>
    request<SameZoneRdsConfig>("/same-zone-rds", { method: "PUT", body: JSON.stringify(body) }),
  listZoneRdsConfigs: (nodeId?: string) =>
    request<ZoneRdsConfig[]>(`/zone-rds-configs${nodeId ? `?node_id=${nodeId}` : ""}`),
  createZoneRdsConfig: (body: Omit<ZoneRdsConfig, "id" | "connection_status">) =>
    request<ZoneRdsConfig>("/zone-rds-configs", { method: "POST", body: JSON.stringify(body) }),
  updateZoneRdsConfig: (id: string, body: Omit<ZoneRdsConfig, "id" | "connection_status">) =>
    request<ZoneRdsConfig>(`/zone-rds-configs/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteZoneRdsConfig: (id: string) => request<void>(`/zone-rds-configs/${id}`, { method: "DELETE" }),

  // alias nodes
  listAliasNodes: () => request<AliasNode[]>("/alias-nodes"),
  createAliasNode: (body: Omit<AliasNode, "id" | "created_at">) =>
    request<AliasNode>("/alias-nodes", { method: "POST", body: JSON.stringify(body) }),
  updateAliasNode: (id: string, body: Omit<AliasNode, "id" | "created_at">) =>
    request<AliasNode>(`/alias-nodes/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteAliasNode: (id: string) => request<void>(`/alias-nodes/${id}`, { method: "DELETE" }),
  listDeviceAssignments: (nodeId: string) =>
    request<NodeDeviceAssignment[]>(`/alias-nodes/${nodeId}/device-assignments`),
  createDeviceAssignment: (nodeId: string, deviceId: string) =>
    request<NodeDeviceAssignment>("/alias-nodes/device-assignments", {
      method: "POST",
      body: JSON.stringify({ node_id: nodeId, device_id: deviceId }),
    }),
  deleteDeviceAssignment: (id: string) =>
    request<void>(`/alias-nodes/device-assignments/${id}`, { method: "DELETE" }),

  // alias devices / connectors
  listAliasDevices: () => request<AliasDevice[]>("/alias-devices"),
  createAliasDevice: (body: Omit<AliasDevice, "id" | "created_at">) =>
    request<AliasDevice>("/alias-devices", { method: "POST", body: JSON.stringify(body) }),
  updateAliasDevice: (id: string, body: Omit<AliasDevice, "id" | "created_at">) =>
    request<AliasDevice>(`/alias-devices/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteAliasDevice: (id: string) => request<void>(`/alias-devices/${id}`, { method: "DELETE" }),
  listAliasConnectors: (deviceId?: string) =>
    request<AliasConnector[]>(`/alias-connectors${deviceId ? `?device_id=${deviceId}` : ""}`),
  createAliasConnector: (deviceId: string, connectorLabel: string) =>
    request<AliasConnector>("/alias-connectors", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId, connector_label: connectorLabel }),
    }),
  updateAliasConnector: (id: string, connectorLabel: string) =>
    request<AliasConnector>(`/alias-connectors/${id}`, {
      method: "PUT",
      body: JSON.stringify({ connector_label: connectorLabel }),
    }),
  deleteAliasConnector: (id: string) => request<void>(`/alias-connectors/${id}`, { method: "DELETE" }),

  // real senders / alias senders
  listRealSenders: (params?: { labelContains?: string; mediaType?: MediaType }) => {
    const qs = new URLSearchParams();
    if (params?.labelContains) qs.set("label_contains", params.labelContains);
    if (params?.mediaType) qs.set("media_type", params.mediaType);
    const q = qs.toString();
    return request<RealSender[]>(`/real-senders${q ? `?${q}` : ""}`);
  },
  getRealSender: (id: string) => request<RealSenderDetail>(`/real-senders/${id}`),
  listAliasSenders: (connectorId?: string) =>
    request<AliasSender[]>(`/alias-senders${connectorId ? `?connector_id=${connectorId}` : ""}`),
  getAliasSender: (id: string) => request<AliasSenderDetail>(`/alias-senders/${id}`),
  createAliasSender: (body: {
    connector_id: string;
    real_sender_id: string;
    media_type?: MediaType;
    description?: string;
  }) => request<AliasSender>("/alias-senders", { method: "POST", body: JSON.stringify(body) }),
  updateAliasSender: (
    id: string,
    body: { connector_id?: string; description?: string; media_type?: MediaType },
  ) => request<AliasSender>(`/alias-senders/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteAliasSender: (id: string) => request<void>(`/alias-senders/${id}`, { method: "DELETE" }),

  // system
  systemInfo: () => request<SystemInfo>("/system/info"),
  updateWebPort: (webPort: number) =>
    request<{ status: string; message: string }>("/system/web-port", {
      method: "PUT",
      body: JSON.stringify({ web_port: webPort }),
    }),
  exportDbUrl: () => `${BASE}/system/db/export`,
  importDb: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/system/db/import`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  resetDatabase: () => request<{ status: string; message: string }>("/system/reset", { method: "POST" }),
  getLogs: (lines = 100) => request<{ lines: string[] }>(`/system/logs?lines=${lines}`),
  downloadLogsUrl: () => `${BASE}/system/logs/download`,
};
