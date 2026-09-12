import { useState } from "react";
import { AliasDevicesView } from "./views/AliasDevicesView";
import { AliasNodesView } from "./views/AliasNodesView";
import { AliasSendersView } from "./views/AliasSendersView";
import { DashboardView } from "./views/DashboardView";
import { RdsConfigView } from "./views/RdsConfigView";
import { SystemSettingsView } from "./views/SystemSettingsView";

const MENU = [
  { key: "dashboard", label: "ダッシュボード" },
  { key: "rds", label: "RDS登録管理" },
  { key: "nodes", label: "Alias Nodeの作成管理" },
  { key: "devices", label: "Alias Device/Connectorの作成管理" },
  { key: "senders", label: "Alias Senderの作成管理" },
  { key: "system", label: "システム設定" },
] as const;

type ViewKey = (typeof MENU)[number]["key"];

export default function App() {
  const [view, setView] = useState<ViewKey>("dashboard");

  return (
    <div className="flex h-full">
      <aside className="w-56 bg-panel border-r border-border flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <div className="text-sm font-bold text-gray-100">Alias Unit Server</div>
          <div className="text-[10px] text-gray-500">Alias Sender PoC</div>
        </div>
        <nav className="flex-1 py-2">
          {MENU.map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              className={`w-full text-left px-4 py-2 text-xs border-l-2 ${
                view === item.key
                  ? "border-accent bg-panelHeader text-white"
                  : "border-transparent text-gray-400 hover:bg-panelHeader hover:text-gray-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto p-4">
        {view === "dashboard" && <DashboardView />}
        {view === "rds" && <RdsConfigView />}
        {view === "nodes" && <AliasNodesView />}
        {view === "devices" && <AliasDevicesView />}
        {view === "senders" && <AliasSendersView />}
        {view === "system" && <SystemSettingsView />}
      </main>
    </div>
  );
}
