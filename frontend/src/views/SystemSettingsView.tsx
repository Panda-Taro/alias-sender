import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "../api";
import { Panel } from "../components/Panel";

export function SystemSettingsView() {
  const systemInfo = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });
  const fileInput = useRef<HTMLInputElement>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const onImport = async () => {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    try {
      const res = await api.importDb(file);
      setImportMessage(res.message ?? "インポート完了");
    } catch (e) {
      setImportMessage(`失敗: ${(e as Error).message}`);
    }
  };

  return (
    <div className="space-y-3">
      <Panel title="データベース エクスポート / インポート">
        <div className="mb-3">
          <a
            className="bg-accent px-3 py-1 rounded text-white inline-block"
            href={api.exportDbUrl()}
            download
          >
            SQLiteファイルをダウンロード
          </a>
        </div>
        <div className="flex items-center gap-2">
          <input ref={fileInput} type="file" accept=".db" className="text-gray-300" />
          <button className="bg-accent px-3 py-1 rounded text-white" onClick={onImport}>
            アップロードしてインポート
          </button>
        </div>
        {importMessage && <div className="text-gray-400 mt-2">{importMessage}</div>}
        <div className="text-gray-500 mt-2">
          ※ インポート後はバックグラウンドエンジンを完全に再同期させるため、コンテナの再起動を推奨します。
        </div>
      </Panel>

      <Panel title="OS情報">
        <div>IPアドレス: {systemInfo.data?.os_ip_addresses.join(", ")}</div>
        <div>WebGUIポート: {systemInfo.data?.web_port}</div>
        <div>Node APIポート開始番号: {systemInfo.data?.node_api_port_start}</div>
        <div className="text-gray-500 mt-2">※ 参照専用。本システムからの設定変更は行いません。</div>
      </Panel>
    </div>
  );
}
