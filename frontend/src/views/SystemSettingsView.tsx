import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Panel } from "../components/Panel";

export function SystemSettingsView() {
  const qc = useQueryClient();
  const systemInfo = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });
  const fileInput = useRef<HTMLInputElement>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const [webPort, setWebPort] = useState<number>(8000);
  const [portMessage, setPortMessage] = useState<string | null>(null);
  useEffect(() => {
    if (systemInfo.data) setWebPort(systemInfo.data.web_port);
  }, [systemInfo.data]);

  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const logs = useQuery({ queryKey: ["system-logs"], queryFn: () => api.getLogs(100) });

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

  const onSavePort = async () => {
    try {
      const res = await api.updateWebPort(webPort);
      setPortMessage(
        `${res.message} 新しいURL: ${window.location.protocol}//${window.location.hostname}:${webPort}/ に切り替えてください。`,
      );
      qc.invalidateQueries({ queryKey: ["system-info"] });
    } catch (e) {
      setPortMessage(`失敗: ${(e as Error).message}`);
    }
  };

  const onReset = async () => {
    const confirmed = window.confirm(
      "データベースを初期化します。AliasNode/Device/Connector/Senderおよび同一ゾーン・他ゾーンRDSの設定が" +
        "すべて削除されます(WebGUIポート設定は保持されます)。この操作は取り消せません。よろしいですか？",
    );
    if (!confirmed) return;
    try {
      const res = await api.resetDatabase();
      setResetMessage(res.message);
      qc.invalidateQueries();
    } catch (e) {
      setResetMessage(`失敗: ${(e as Error).message}`);
    }
  };

  return (
    <div className="space-y-3">
      <Panel title="WebGUI/管理APIポート設定">
        <div className="flex flex-wrap gap-2 items-end">
          <input
            type="number"
            className="bg-appbg border border-border rounded px-2 py-1 w-28"
            value={webPort}
            onChange={(e) => setWebPort(Number(e.target.value))}
          />
          <button className="bg-accent px-3 py-1 rounded text-white" onClick={onSavePort}>
            保存して切替
          </button>
        </div>
        {portMessage && <div className="text-gray-300 mt-2">{portMessage}</div>}
        <div className="text-gray-500 mt-2">
          ※ 保存後、このWebGUI自体が新しいポートで再起動します(プロセス再起動は不要)。ブラウザで新しいURLに
          アクセスし直してください。
        </div>
      </Panel>

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

      <Panel title="初期化">
        <button className="bg-offline px-3 py-1 rounded text-white" onClick={onReset}>
          データベースを初期化(全削除)
        </button>
        {resetMessage && <div className="text-gray-300 mt-2">{resetMessage}</div>}
        <div className="text-gray-500 mt-2">
          ※ AliasNode/Device/Connector/Sender、RDS設定を含む全データを削除します。WebGUIポート設定のみ保持されます。
        </div>
      </Panel>

      <Panel title="OS情報">
        <div>IPアドレス: {systemInfo.data?.os_ip_addresses.join(", ")}</div>
        <div>Node APIポート開始番号: {systemInfo.data?.node_api_port_start}</div>
        <div className="text-gray-500 mt-2">※ 参照専用。本システムからの設定変更は行いません。</div>
      </Panel>

      <Panel
        title="ログ表示"
        action={
          <div className="flex gap-2">
            <button
              className="text-gray-300 hover:text-white text-xs"
              onClick={() => qc.invalidateQueries({ queryKey: ["system-logs"] })}
            >
              更新
            </button>
            <a className="text-gray-300 hover:text-white text-xs" href={api.downloadLogsUrl()} download>
              ダウンロード
            </a>
          </div>
        }
      >
        <pre className="bg-appbg border border-border rounded p-2 text-[11px] max-h-20 overflow-y-auto whitespace-pre-wrap">
          {logs.data?.lines.length ? [...logs.data.lines].reverse().join("\n") : "(ログがありません)"}
        </pre>
        <div className="text-gray-500 mt-2">※ 最新100件を新しい順で表示します。</div>
      </Panel>
    </div>
  );
}
