import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type AliasNode, type ZoneRdsConfig } from "../api";
import { Panel } from "../components/Panel";
import { StatusDot } from "../components/StatusDot";

type ZoneEditForm = Omit<ZoneRdsConfig, "id" | "connection_status">;

export function RdsConfigView() {
  const qc = useQueryClient();
  const sameZone = useQuery({ queryKey: ["same-zone-rds"], queryFn: api.getSameZoneRds });
  const nodes = useQuery({ queryKey: ["alias-nodes"], queryFn: api.listAliasNodes });
  const zoneConfigs = useQuery({ queryKey: ["zone-rds-configs"], queryFn: () => api.listZoneRdsConfigs() });
  const rdsStatus = useQuery({ queryKey: ["rds-status"], queryFn: api.rdsStatus });

  const [sz, setSz] = useState<{ enabled: boolean; ip_address: string; port: number | null; query_api_version: string }>({
    enabled: false,
    ip_address: "",
    port: 8010,
    query_api_version: "v1.3",
  });
  useEffect(() => {
    if (sameZone.data) setSz(sameZone.data);
  }, [sameZone.data]);

  const [newZone, setNewZone] = useState<Omit<ZoneRdsConfig, "id" | "connection_status">>({
    node_id: "",
    registration_api_enabled: true,
    registration_ip_address: "",
    registration_port: 8010,
    registration_api_version: "v1.3",
    registration_source_port: null,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<ZoneEditForm | null>(null);

  const saveSameZone = async () => {
    await api.putSameZoneRds(sz);
    qc.invalidateQueries({ queryKey: ["same-zone-rds"] });
  };

  const addZoneConfig = async () => {
    try {
      await api.createZoneRdsConfig(newZone);
      qc.invalidateQueries({ queryKey: ["zone-rds-configs"] });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const startEdit = (z: ZoneRdsConfig) => {
    setEditingId(z.id);
    setEditForm({
      node_id: z.node_id,
      registration_api_enabled: z.registration_api_enabled,
      registration_ip_address: z.registration_ip_address,
      registration_port: z.registration_port,
      registration_api_version: z.registration_api_version,
      registration_source_port: z.registration_source_port,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(null);
  };

  const saveEdit = async () => {
    if (!editingId || !editForm) return;
    try {
      await api.updateZoneRdsConfig(editingId, editForm);
      qc.invalidateQueries({ queryKey: ["zone-rds-configs"] });
      cancelEdit();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const removeZoneConfig = async (id: string) => {
    await api.deleteZoneRdsConfig(id);
    qc.invalidateQueries({ queryKey: ["zone-rds-configs"] });
  };

  const nodeLabel = (id: string) => nodes.data?.find((n: AliasNode) => n.id === id)?.alias_node_label ?? id;
  const zoneDetail = (id: string) => rdsStatus.data?.other_zones.find((z) => z.id === id);

  return (
    <div className="space-y-3">
      <Panel title="同一ゾーンRDS情報 (Query API送信先)">
        <div className="flex flex-wrap gap-2 items-end">
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={sz.enabled} onChange={(e) => setSz({ ...sz, enabled: e.target.checked })} />
            ON/OFF
          </label>
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="IPアドレス"
            value={sz.ip_address}
            onChange={(e) => setSz({ ...sz, ip_address: e.target.value })}
          />
          <input
            type="number"
            className="bg-appbg border border-border rounded px-2 py-1 w-24"
            placeholder="ポート"
            value={sz.port ?? ""}
            onChange={(e) => setSz({ ...sz, port: Number(e.target.value) })}
          />
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={sz.query_api_version}
            onChange={(e) => setSz({ ...sz, query_api_version: e.target.value })}
          >
            {["v1.1", "v1.2", "v1.3"].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <button className="bg-accent px-3 py-1 rounded text-white" onClick={saveSameZone}>
            保存
          </button>
          <StatusDot online={sameZone.data?.connection_status === "online"} />
        </div>
        {rdsStatus.data?.same_zone.last_error && (
          <div className="text-offline mt-2">エラー: {rdsStatus.data.same_zone.last_error}</div>
        )}
      </Panel>

      <Panel title="他ゾーンRDS情報 (Registration API送信先、Alias Node単位で複数登録可)">
        <div className="flex flex-wrap gap-2 items-end mb-3">
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={newZone.node_id}
            onChange={(e) => setNewZone({ ...newZone, node_id: e.target.value })}
          >
            <option value="">Alias Nodeを選択</option>
            {nodes.data?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.alias_node_label}
              </option>
            ))}
          </select>
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="IPアドレス"
            value={newZone.registration_ip_address}
            onChange={(e) => setNewZone({ ...newZone, registration_ip_address: e.target.value })}
          />
          <input
            type="number"
            className="bg-appbg border border-border rounded px-2 py-1 w-24"
            placeholder="ポート"
            value={newZone.registration_port}
            onChange={(e) => setNewZone({ ...newZone, registration_port: Number(e.target.value) })}
          />
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={newZone.registration_api_version}
            onChange={(e) => setNewZone({ ...newZone, registration_api_version: e.target.value })}
          >
            {["v1.1", "v1.2", "v1.3"].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <input
            type="number"
            className="bg-appbg border border-border rounded px-2 py-1 w-28"
            placeholder="送信元ポート(任意)"
            value={newZone.registration_source_port ?? ""}
            onChange={(e) =>
              setNewZone({ ...newZone, registration_source_port: e.target.value === "" ? null : Number(e.target.value) })
            }
          />
          <button className="bg-accent px-3 py-1 rounded text-white" onClick={addZoneConfig} disabled={!newZone.node_id}>
            追加
          </button>
        </div>

        <table className="w-full">
          <thead className="text-gray-400 text-left">
            <tr>
              <th className="py-1">状態</th>
              <th>Alias Node</th>
              <th>IP:Port</th>
              <th>Ver</th>
              <th>送信元Port</th>
              <th>Sender登録数</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {zoneConfigs.data?.map((z) => {
              const detail = zoneDetail(z.id);
              const isEditing = editingId === z.id;
              return (
                <tr key={z.id} className="border-t border-border align-top">
                  {isEditing && editForm ? (
                    <>
                      <td className="py-1">
                        <StatusDot online={z.connection_status === "online"} />
                      </td>
                      <td>
                        <select
                          className="bg-appbg border border-border rounded px-1"
                          value={editForm.node_id}
                          onChange={(e) => setEditForm({ ...editForm, node_id: e.target.value })}
                        >
                          {nodes.data?.map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.alias_node_label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="flex gap-1">
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editForm.registration_ip_address}
                          onChange={(e) => setEditForm({ ...editForm, registration_ip_address: e.target.value })}
                        />
                        <input
                          type="number"
                          className="bg-appbg border border-border rounded px-1 w-16"
                          value={editForm.registration_port}
                          onChange={(e) => setEditForm({ ...editForm, registration_port: Number(e.target.value) })}
                        />
                      </td>
                      <td>
                        <select
                          className="bg-appbg border border-border rounded px-1"
                          value={editForm.registration_api_version}
                          onChange={(e) => setEditForm({ ...editForm, registration_api_version: e.target.value })}
                        >
                          {["v1.1", "v1.2", "v1.3"].map((v) => (
                            <option key={v} value={v}>
                              {v}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <input
                          type="number"
                          className="bg-appbg border border-border rounded px-1 w-20"
                          placeholder="任意"
                          value={editForm.registration_source_port ?? ""}
                          onChange={(e) =>
                            setEditForm({
                              ...editForm,
                              registration_source_port: e.target.value === "" ? null : Number(e.target.value),
                            })
                          }
                        />
                      </td>
                      <td>-</td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={saveEdit}>
                          保存
                        </button>
                        <button className="text-gray-400" onClick={cancelEdit}>
                          取消
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-1">
                        <StatusDot online={z.connection_status === "online"} />
                      </td>
                      <td>{nodeLabel(z.node_id)}</td>
                      <td>
                        {z.registration_ip_address}:{z.registration_port}
                      </td>
                      <td>{z.registration_api_version}</td>
                      <td>{z.registration_source_port ?? "-"}</td>
                      <td>
                        {detail ? `${detail.senders_ok}/${detail.senders_total}` : "-"}
                      </td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={() => startEdit(z)}>
                          編集
                        </button>
                        <button className="text-offline" onClick={() => removeZoneConfig(z.id)}>
                          削除
                        </button>
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {zoneConfigs.data?.some((z) => zoneDetail(z.id)?.last_error) && (
          <div className="mt-2 space-y-1">
            {zoneConfigs.data
              .filter((z) => zoneDetail(z.id)?.last_error)
              .map((z) => (
                <div key={z.id} className="text-offline">
                  {nodeLabel(z.node_id)}: {zoneDetail(z.id)?.last_error}
                </div>
              ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
