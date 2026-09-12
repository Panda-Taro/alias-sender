import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type MediaType } from "../api";
import { Panel } from "../components/Panel";
import { StatusDot } from "../components/StatusDot";

const MEDIA_TYPES: MediaType[] = ["video", "audio", "ancillary"];

export function AliasSendersView() {
  const qc = useQueryClient();
  const devices = useQuery({ queryKey: ["alias-devices"], queryFn: api.listAliasDevices });
  const connectors = useQuery({ queryKey: ["alias-connectors"], queryFn: () => api.listAliasConnectors() });
  const aliasSenders = useQuery({ queryKey: ["alias-senders"], queryFn: () => api.listAliasSenders() });

  const [labelFilter, setLabelFilter] = useState("");
  const [mediaFilter, setMediaFilter] = useState<MediaType | "">("");
  const realSenders = useQuery({
    queryKey: ["real-senders", labelFilter, mediaFilter],
    queryFn: () => api.listRealSenders({ labelContains: labelFilter || undefined, mediaType: mediaFilter || undefined }),
  });

  const [form, setForm] = useState<{
    connector_id: string;
    real_sender_id: string;
    media_type: MediaType | "";
    description: string;
  }>({ connector_id: "", real_sender_id: "", media_type: "", description: "" });

  const create = async () => {
    try {
      await api.createAliasSender({
        connector_id: form.connector_id,
        real_sender_id: form.real_sender_id,
        media_type: form.media_type || undefined,
        description: form.description,
      });
      qc.invalidateQueries({ queryKey: ["alias-senders"] });
      setForm({ ...form, real_sender_id: "", description: "" });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const updateDescription = async (id: string, description: string) => {
    await api.updateAliasSender(id, { description });
    qc.invalidateQueries({ queryKey: ["alias-senders"] });
  };

  const updateMediaType = async (id: string, media_type: MediaType) => {
    try {
      await api.updateAliasSender(id, { media_type });
      qc.invalidateQueries({ queryKey: ["alias-senders"] });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const updateConnector = async (id: string, connector_id: string) => {
    try {
      await api.updateAliasSender(id, { connector_id });
      qc.invalidateQueries({ queryKey: ["alias-senders"] });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const remove = async (id: string) => {
    await api.deleteAliasSender(id);
    qc.invalidateQueries({ queryKey: ["alias-senders"] });
  };

  return (
    <div className="space-y-3">
      <Panel title="Alias Sender作成">
        <div className="flex flex-wrap gap-2 items-end mb-2">
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={form.connector_id}
            onChange={(e) => setForm({ ...form, connector_id: e.target.value })}
          >
            <option value="">Connectorを選択</option>
            {connectors.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {devices.data?.find((d) => d.id === c.device_id)?.alias_device_label} / {c.connector_label}
              </option>
            ))}
          </select>
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={form.media_type}
            onChange={(e) => setForm({ ...form, media_type: e.target.value as MediaType })}
          >
            <option value="">media_type(初期値=RealSenderの自動判定を使用)</option>
            {MEDIA_TYPES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="description (他ゾーンRDSへ広告)"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>

        <div className="flex flex-wrap gap-2 items-end mb-2">
          <input
            className="bg-appbg border border-border rounded px-2 py-1"
            placeholder="Real Sender 文字列フィルター"
            value={labelFilter}
            onChange={(e) => setLabelFilter(e.target.value)}
          />
          <select
            className="bg-appbg border border-border rounded px-2 py-1"
            value={mediaFilter}
            onChange={(e) => setMediaFilter(e.target.value as MediaType | "")}
          >
            <option value="">media_typeフィルターなし</option>
            {MEDIA_TYPES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <table className="w-full mb-2">
          <thead className="text-gray-400 text-left">
            <tr>
              <th />
              <th>状態</th>
              <th>Real Sender Label</th>
              <th>media_type検出</th>
            </tr>
          </thead>
          <tbody>
            {realSenders.data?.map((rs) => (
              <tr
                key={rs.id}
                className={`border-t border-border cursor-pointer ${form.real_sender_id === rs.id ? "bg-panelHeader" : ""}`}
                onClick={() => setForm({ ...form, real_sender_id: rs.id })}
              >
                <td>
                  <input type="radio" checked={form.real_sender_id === rs.id} readOnly />
                </td>
                <td>
                  <StatusDot online={rs.status === "online"} />
                </td>
                <td className="py-1">{rs.nmos_sender_label}</td>
                <td>{rs.media_type_detected ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <button
          className="bg-accent px-3 py-1 rounded text-white"
          onClick={create}
          disabled={!form.connector_id || !form.real_sender_id}
        >
          Alias Sender作成
        </button>
      </Panel>

      <Panel title="Alias Sender一覧">
        <table className="w-full">
          <thead className="text-gray-400 text-left">
            <tr>
              <th>状態</th>
              <th>Label</th>
              <th>Connector</th>
              <th>media_type</th>
              <th>Description</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {aliasSenders.data?.map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="py-1">
                  <StatusDot online={s.sync_status === "online"} />
                </td>
                <td>{s.label}</td>
                <td>
                  <select
                    className="bg-appbg border border-border rounded px-1"
                    value={s.connector_id}
                    onChange={(e) => updateConnector(s.id, e.target.value)}
                  >
                    {connectors.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {devices.data?.find((d) => d.id === c.device_id)?.alias_device_label} / {c.connector_label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    className="bg-appbg border border-border rounded px-1"
                    value={s.media_type}
                    onChange={(e) => updateMediaType(s.id, e.target.value as MediaType)}
                  >
                    {MEDIA_TYPES.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    className="bg-appbg border border-border rounded px-1 w-full"
                    defaultValue={s.description}
                    onBlur={(e) => updateDescription(s.id, e.target.value)}
                  />
                </td>
                <td>
                  <button className="text-offline" onClick={() => remove(s.id)}>
                    削除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
