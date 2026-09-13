import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Panel } from "../components/Panel";

export function AliasDevicesView() {
  const qc = useQueryClient();
  const devices = useQuery({ queryKey: ["alias-devices"], queryFn: api.listAliasDevices });
  const connectors = useQuery({ queryKey: ["alias-connectors"], queryFn: () => api.listAliasConnectors() });
  const nodes = useQuery({ queryKey: ["alias-nodes"], queryFn: api.listAliasNodes });

  const [deviceForm, setDeviceForm] = useState({ alias_device_label: "", alias_device_description: "" });
  const [connectorForm, setConnectorForm] = useState({ device_id: "", connector_label: "" });

  const [editingDeviceId, setEditingDeviceId] = useState<string | null>(null);
  const [editDeviceForm, setEditDeviceForm] = useState({ alias_device_label: "", alias_device_description: "" });

  const [editingConnectorId, setEditingConnectorId] = useState<string | null>(null);
  const [editConnectorLabel, setEditConnectorLabel] = useState("");

  // X-Y crosspoint: fetch assignments for every node (small scale PoC, fine to fetch per node)
  const assignmentsQuery = useQuery({
    queryKey: ["all-device-assignments", nodes.data?.map((n) => n.id).join(",")],
    queryFn: async () => {
      if (!nodes.data) return [];
      const lists = await Promise.all(nodes.data.map((n) => api.listDeviceAssignments(n.id)));
      return lists.flat();
    },
    enabled: !!nodes.data,
  });

  const createDevice = async () => {
    await api.createAliasDevice(deviceForm);
    qc.invalidateQueries({ queryKey: ["alias-devices"] });
    setDeviceForm({ alias_device_label: "", alias_device_description: "" });
  };

  const removeDevice = async (id: string) => {
    await api.deleteAliasDevice(id);
    qc.invalidateQueries({ queryKey: ["alias-devices"] });
  };

  const startEditDevice = (id: string, label: string, description: string) => {
    setEditingDeviceId(id);
    setEditDeviceForm({ alias_device_label: label, alias_device_description: description });
  };

  const saveEditDevice = async () => {
    if (!editingDeviceId) return;
    await api.updateAliasDevice(editingDeviceId, editDeviceForm);
    qc.invalidateQueries({ queryKey: ["alias-devices"] });
    setEditingDeviceId(null);
  };

  const createConnector = async () => {
    await api.createAliasConnector(connectorForm.device_id, connectorForm.connector_label);
    qc.invalidateQueries({ queryKey: ["alias-connectors"] });
    setConnectorForm({ ...connectorForm, connector_label: "" });
  };

  const removeConnector = async (id: string) => {
    await api.deleteAliasConnector(id);
    qc.invalidateQueries({ queryKey: ["alias-connectors"] });
  };

  const startEditConnector = (id: string, label: string) => {
    setEditingConnectorId(id);
    setEditConnectorLabel(label);
  };

  const saveEditConnector = async () => {
    if (!editingConnectorId) return;
    await api.updateAliasConnector(editingConnectorId, editConnectorLabel);
    qc.invalidateQueries({ queryKey: ["alias-connectors"] });
    setEditingConnectorId(null);
  };

  const toggleAssignment = async (nodeId: string, deviceId: string) => {
    const existing = assignmentsQuery.data?.find((a) => a.node_id === nodeId && a.device_id === deviceId);
    if (existing) {
      await api.deleteDeviceAssignment(existing.id);
    } else {
      await api.createDeviceAssignment(nodeId, deviceId);
    }
    qc.invalidateQueries({ queryKey: ["all-device-assignments"] });
  };

  return (
    <div className="space-y-3">
      <Panel title="Alias Device 作成・削除">
        <div className="flex flex-wrap gap-2 items-end mb-3">
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="label:回線名"
            value={deviceForm.alias_device_label}
            onChange={(e) => setDeviceForm({ ...deviceForm, alias_device_label: e.target.value })}
          />
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="description:回線種別"
            value={deviceForm.alias_device_description}
            onChange={(e) => setDeviceForm({ ...deviceForm, alias_device_description: e.target.value })}
          />
          <button className="bg-accent px-3 py-1 rounded text-white" onClick={createDevice} disabled={!deviceForm.alias_device_label}>
            作成
          </button>
        </div>
        <table className="w-full">
          <thead className="text-gray-400 text-left">
            <tr>
              <th>Label</th>
              <th>Description</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {devices.data?.map((d) => {
              const isEditing = editingDeviceId === d.id;
              return (
                <tr key={d.id} className="border-t border-border">
                  {isEditing ? (
                    <>
                      <td className="py-1">
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editDeviceForm.alias_device_label}
                          onChange={(e) => setEditDeviceForm({ ...editDeviceForm, alias_device_label: e.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editDeviceForm.alias_device_description}
                          onChange={(e) =>
                            setEditDeviceForm({ ...editDeviceForm, alias_device_description: e.target.value })
                          }
                        />
                      </td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={saveEditDevice}>
                          保存
                        </button>
                        <button className="text-gray-400" onClick={() => setEditingDeviceId(null)}>
                          取消
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-1">{d.alias_device_label}</td>
                      <td>{d.alias_device_description}</td>
                      <td className="flex gap-2">
                        <button
                          className="text-accent"
                          onClick={() => startEditDevice(d.id, d.alias_device_label, d.alias_device_description)}
                        >
                          編集
                        </button>
                        <button className="text-offline" onClick={() => removeDevice(d.id)}>
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
      </Panel>

      <Panel title="Alias Connector 作成・削除 (Device配下、最大3 Sender/Connector)">
        <div className="flex flex-wrap gap-2 items-end mb-3">
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={connectorForm.device_id}
            onChange={(e) => setConnectorForm({ ...connectorForm, device_id: e.target.value })}
          >
            <option value="">Alias Deviceを選択</option>
            {devices.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.alias_device_label}
              </option>
            ))}
          </select>
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="Connector label (例: SB1, KDDI1)"
            value={connectorForm.connector_label}
            onChange={(e) => setConnectorForm({ ...connectorForm, connector_label: e.target.value })}
          />
          <button
            className="bg-accent px-3 py-1 rounded text-white"
            onClick={createConnector}
            disabled={!connectorForm.device_id || !connectorForm.connector_label}
          >
            作成
          </button>
        </div>
        <table className="w-full">
          <thead className="text-gray-400 text-left">
            <tr>
              <th>Connector</th>
              <th>所属Device</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {connectors.data?.map((c) => {
              const isEditing = editingConnectorId === c.id;
              return (
                <tr key={c.id} className="border-t border-border">
                  {isEditing ? (
                    <>
                      <td className="py-1">
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editConnectorLabel}
                          onChange={(e) => setEditConnectorLabel(e.target.value)}
                        />
                      </td>
                      <td>{devices.data?.find((d) => d.id === c.device_id)?.alias_device_label}</td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={saveEditConnector}>
                          保存
                        </button>
                        <button className="text-gray-400" onClick={() => setEditingConnectorId(null)}>
                          取消
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-1">{c.connector_label}</td>
                      <td>{devices.data?.find((d) => d.id === c.device_id)?.alias_device_label}</td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={() => startEditConnector(c.id, c.connector_label)}>
                          編集
                        </button>
                        <button className="text-offline" onClick={() => removeConnector(c.id)}>
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
      </Panel>

      <Panel title="X-Yクロスポイント: Alias Node(X) × Alias Device(Y)">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-left text-gray-400">Node ＼ Device</th>
              {devices.data?.map((d) => (
                <th key={d.id} className="text-gray-400 px-2">
                  {d.alias_device_label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {nodes.data?.map((n) => (
              <tr key={n.id} className="border-t border-border">
                <td className="text-gray-300 py-1">{n.alias_node_label}</td>
                {devices.data?.map((d) => {
                  const checked = !!assignmentsQuery.data?.find((a) => a.node_id === n.id && a.device_id === d.id);
                  return (
                    <td key={d.id} className="text-center">
                      <input type="checkbox" checked={checked} onChange={() => toggleAssignment(n.id, d.id)} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-gray-500 mt-2">
          1つのAliasDeviceを複数のAliasNodeに割り当てできます(M:N, REQ-C03)。
        </div>
      </Panel>
    </div>
  );
}
