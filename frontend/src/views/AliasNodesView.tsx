import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type AliasNode } from "../api";
import { Panel } from "../components/Panel";

type NodeForm = Omit<AliasNode, "id" | "created_at">;

export function AliasNodesView() {
  const qc = useQueryClient();
  const nodes = useQuery({ queryKey: ["alias-nodes"], queryFn: api.listAliasNodes });
  const zoneConfigs = useQuery({ queryKey: ["zone-rds-configs"], queryFn: () => api.listZoneRdsConfigs() });

  const [form, setForm] = useState<NodeForm>({
    alias_node_label: "",
    alias_node_description: "",
    node_api_enabled: true,
    node_api_port: 10080,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<NodeForm | null>(null);

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

  const startEdit = (n: AliasNode) => {
    setEditingId(n.id);
    setEditForm({
      alias_node_label: n.alias_node_label,
      alias_node_description: n.alias_node_description,
      node_api_enabled: n.node_api_enabled,
      node_api_port: n.node_api_port,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(null);
  };

  const saveEdit = async () => {
    if (!editingId || !editForm) return;
    try {
      await api.updateAliasNode(editingId, editForm);
      qc.invalidateQueries({ queryKey: ["alias-nodes"] });
      cancelEdit();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const linkedRdsCount = (nodeId: string) => zoneConfigs.data?.filter((z) => z.node_id === nodeId).length ?? 0;

  return (
    <div className="space-y-3">
      <Panel title="新規Alias Node作成">
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
            value={form.node_api_port ?? ""}
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

      <Panel title="Alias Node一覧">
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
            {nodes.data?.map((n) => {
              const isEditing = editingId === n.id;
              return (
                <tr key={n.id} className="border-t border-border">
                  {isEditing && editForm ? (
                    <>
                      <td className="py-1">
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editForm.alias_node_label}
                          onChange={(e) => setEditForm({ ...editForm, alias_node_label: e.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          className="bg-appbg border border-border rounded px-1 w-28"
                          value={editForm.alias_node_description}
                          onChange={(e) => setEditForm({ ...editForm, alias_node_description: e.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={editForm.node_api_enabled}
                          onChange={(e) => setEditForm({ ...editForm, node_api_enabled: e.target.checked })}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          className="bg-appbg border border-border rounded px-1 w-20"
                          value={editForm.node_api_port ?? ""}
                          onChange={(e) => setEditForm({ ...editForm, node_api_port: Number(e.target.value) })}
                        />
                      </td>
                      <td>{linkedRdsCount(n.id)}</td>
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
                      <td className="py-1">{n.alias_node_label}</td>
                      <td>{n.alias_node_description}</td>
                      <td>{n.node_api_enabled ? "ON" : "OFF"}</td>
                      <td>{n.node_api_port}</td>
                      <td>{linkedRdsCount(n.id)}</td>
                      <td className="flex gap-2">
                        <button className="text-accent" onClick={() => startEdit(n)}>
                          編集
                        </button>
                        <button className="text-offline" onClick={() => remove(n.id)}>
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
        <div className="text-gray-500 mt-2">
          ※ AliasNodeの削除は、紐づくZoneRdsConfig(他ゾーンRDS)が存在しないことが条件です(REQ-B04)。
        </div>
      </Panel>
    </div>
  );
}
