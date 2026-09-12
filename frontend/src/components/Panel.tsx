import type { ReactNode } from "react";

export function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="bg-panel border border-border rounded-md mb-3">
      <div className="bg-panelHeader px-3 py-1.5 rounded-t-md flex items-center justify-between border-b border-border">
        <span className="font-semibold text-gray-300 text-xs uppercase tracking-wide">{title}</span>
        {action}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}
