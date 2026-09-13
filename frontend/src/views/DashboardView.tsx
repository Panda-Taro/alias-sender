import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Panel } from "../components/Panel";
import { StatusDot } from "../components/StatusDot";

export function DashboardView() {
  const rdsStatus = useQuery({ queryKey: ["rds-status"], queryFn: api.rdsStatus });
  const sameZoneTree = useQuery({ queryKey: ["same-zone-tree"], queryFn: api.sameZoneTree });
  const aliasNodeTree = useQuery({ queryKey: ["alias-node-tree"], queryFn: api.aliasNodeTree });
  const systemInfo = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });

  const [selectedRealNode, setSelectedRealNode] = useState<string | null>(null);
  const [openDevices, setOpenDevices] = useState<Set<string>>(new Set());
  const [openConnector, setOpenConnector] = useState<{ sdp: string; label: string } | null>(null);

  const toggleDevice = (id: string) => {
    setOpenDevices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedNodeData = sameZoneTree.data?.find((n) => n.nmos_node_id === selectedRealNode);

  return (
    <div className="grid grid-cols-2 gap-3">
      <Panel title="① RDS接続情報">
        <div className="mb-2">
          <div className="text-gray-400 mb-1">同一ゾーンRDS</div>
          <div className="flex items-center gap-2">
            <StatusDot online={!!rdsStatus.data?.same_zone.connected} />
            <span>
              {rdsStatus.data?.same_zone.ip_address}:{rdsStatus.data?.same_zone.port} (
              {rdsStatus.data?.same_zone.query_api_version})
            </span>
            {rdsStatus.data?.same_zone.ws_connected && (
              <span className="text-[10px] text-online">WS接続中</span>
            )}
          </div>
        </div>
        <div className="max-h-40 overflow-y-auto">
          <div className="text-gray-400 mb-1">他ゾーンRDS</div>
          {rdsStatus.data?.other_zones.map((z) => (
            <div key={z.id} className="flex items-center gap-2 py-0.5">
              <StatusDot online={z.connected} />
              <span>
                {z.ip_address}:{z.port} ({z.registration_api_version})
              </span>
            </div>
          ))}
          {rdsStatus.data?.other_zones.length === 0 && <div className="text-gray-500">未設定</div>}
        </div>
      </Panel>

      <Panel title="③ OS情報・本システム設定情報">
        <div>OS IPアドレス: {systemInfo.data?.os_ip_addresses.join(", ")}</div>
        <div>WebGUIポート: {systemInfo.data?.web_port}</div>
        <div>Node APIポート開始番号: {systemInfo.data?.node_api_port_start}</div>
      </Panel>

      <Panel title="② 本システムDB状態表示 (同一ゾーンRDS Node一覧)">
        <div className="flex gap-2 flex-wrap mb-2">
          {sameZoneTree.data?.map((n) => (
            <button
              key={n.nmos_node_id}
              onClick={() => setSelectedRealNode(n.nmos_node_id)}
              className={`px-2 py-1 rounded border ${
                selectedRealNode === n.nmos_node_id
                  ? "border-accent text-white"
                  : "border-border text-gray-400"
              }`}
            >
              {n.nmos_node_id.slice(0, 8)}
            </button>
          ))}
          {sameZoneTree.data?.length === 0 && <div className="text-gray-500">Node未取得</div>}
        </div>
        {selectedNodeData && (
          <div className="border border-border rounded p-2 max-h-52 overflow-y-auto">
            {selectedNodeData.devices.map((d) => (
              <div key={d.nmos_device_id} className="mb-2">
                <div className="text-gray-400">Device: {d.nmos_device_id}</div>
                {d.senders.map((s) => (
                  <div key={s.id} className="flex items-center gap-2 pl-3">
                    <StatusDot online={s.status === "online"} />
                    <span>{s.nmos_sender_label}</span>
                    <span className="text-gray-500">({s.media_type_detected ?? "?"})</span>
                  </div>
                ))}
                <div className="pl-3 text-gray-500">Receiver: (なし)</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="④ Alias Node情報">
        <div className="max-h-96 overflow-y-auto space-y-2">
          {aliasNodeTree.data?.map((nt) => (
            <div key={nt.node.id} className="border border-border rounded p-2">
              <div className="font-semibold text-gray-200">
                {nt.node.alias_node_label}
                <span className="text-gray-500 font-normal ml-2">Port: {nt.node.node_api_port ?? "-"}</span>
              </div>
              {nt.devices.map((d) => (
                <div key={d.id} className="ml-2 mt-1">
                  <button
                    className="text-gray-300 hover:text-white"
                    onClick={() => toggleDevice(d.id)}
                  >
                    {openDevices.has(d.id) ? "▼" : "▶"} {d.alias_device_label}
                  </button>
                  {openDevices.has(d.id) && (
                    <div className="ml-3 mt-1 space-y-1">
                      {d.connectors.map((c) => (
                        <div key={c.id}>
                          <div className="text-gray-400">{c.connector_label}</div>
                          {c.senders.map((s) => (
                            <button
                              key={s.id}
                              className="flex items-center gap-2 pl-3 w-full text-left hover:bg-panelHeader rounded"
                              onClick={() => {
                                setOpenConnector({ sdp: "", label: s.label });
                                api
                                  .getAliasSender(s.id)
                                  .then((detail) => setOpenConnector({ sdp: detail.sdp_mirrored, label: detail.label }));
                              }}
                            >
                              <StatusDot online={s.sync_status === "online"} />
                              <span>{s.label}</span>
                              <span className="text-gray-500">{s.media_type}</span>
                              <span className="text-gray-500">← {s.real_sender_label}</span>
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
          {aliasNodeTree.data?.length === 0 && <div className="text-gray-500">Alias Node未作成</div>}
        </div>
      </Panel>

      {openConnector && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setOpenConnector(null)}>
          <div className="bg-panel border border-border rounded p-4 w-2/3 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between mb-2">
              <div className="font-semibold">{openConnector.label} - SDP</div>
              <button className="text-gray-400 hover:text-white" onClick={() => setOpenConnector(null)}>
                ✕
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-[11px] bg-appbg p-2 rounded border border-border">
              {openConnector.sdp || "(取得中...)"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
