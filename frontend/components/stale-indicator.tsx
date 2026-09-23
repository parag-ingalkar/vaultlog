export function StaleIndicator({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-warning"
      title="Refreshing data in background"
    >
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning motion-reduce:animate-none" />
      Updating
    </span>
  );
}
