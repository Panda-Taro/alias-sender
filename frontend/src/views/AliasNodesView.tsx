import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Panel } from "../components/Panel";

export function AliasNodesView() {
  const qc = useQueryClient();
  const nodes = useQuery({ queryKey: ["alias-nodes"], queryFn: api.listAliasNodes });
  const zoneConfigs = useQuery({ queryKey: ["zone-rds-configs"], queryFn: () => api.listZoneRdsConfigs() });

  const [form, setForm] = useState({
    alias_node_label: "",
    alias_node_description: "",
    node_api_enabled: true,
    node_api_port: 10080,
  });

  const create = async () => {
    await api.createAliasNode(form);
    qc.invalidateQueries({ queryKey: ["alias-nodes"] });
    setForm({ ...form, alias_node_label: "", alias_node_description: "" });
  };

  const remove = async (id: string) => {
    try {
      await api.deleteAliasNode(id);
      qc.invalidateQueries({ queryKey: ["alias-nodes"] });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const linkedRdsCount = (nodeId: string) => zoneConfigs.data?.filter((z) => z.node_id === nodeId).length ?? 0;

  return (
    <div className="space-y-3">
      <Panel title="新規AliasNode作成">
        <div className="flex flex-wrap gap-2 items-end">
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="Node label"
            value={form.alias_node_label}
            onChange={(e) => setForm({ ...form, alias_node_label: e.target.value })}
          />
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="description"
            value={form.alias_node_description}
            onChange={(e) => setForm({ ...form, alias_node_description: e.target.value })}
          />
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={form.node_api_enabled}
              onChange={(e) => setForm({ ...form, node_api_enabled: e.target.checked })}
            />
            Node API ON
          </label>
          <input
            type="number"
            className="bg-appbg border border-border rounded px-2 py-1 w-28"
            placeholder="node_api_port"
            value={form.node_api_port}
            onChange={(e) => setForm({ ...form, node_api_port: Number(e.target.value) })}
          />
          <button
            className="bg-accent px-3 py-1 rounded text-white"
            onClick={create}
            disabled={!form.alias_node_label}
          >
            作成
          </button>
        </div>
      </Panel>

      <Panel title="AliasNode一覧">
        <table className="w-full">
          <thead className="text-gray-400 text-left">
            <tr>
              <th>Label</th>
              <th>Description</th>
              <th>Node API</th>
              <th>Port</th>
              <th>紐づくRDS数</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {nodes.data?.map((n) => (
              <tr key={n.id} className="border-t border-border">
                <td className="py-1">{n.alias_node_label}</td>
                <td>{n.alias_node_description}</td>
                <td>{n.node_api_enabled ? "ON" : "OFF"}</td>
                <td>{n.node_api_port}</td>
                <td>{linkedRdsCount(n.id)}</td>
                <td>
                  <button className="text-offline" onClick={() => remove(n.id)}>
                    削除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-gray-500 mt-2">
          ※ AliasNodeの削除は、紐づくZoneRdsConfig(他ゾーンRDS)が存在しないことが条件です(REQ-B04)。
        </div>
      </Panel>
    </div>
  );
}
