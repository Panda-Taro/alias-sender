export function StatusDot({ online }: { online: boolean }) {
  return (
    <span
      className="status-dot"
      style={{ backgroundColor: online ? "#22c55e" : "#ef4444" }}
      title={online ? "online" : "offline"}
    />
  );
}
