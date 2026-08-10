export function StaleIndicator({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
      title="Refreshing data in background"
    >
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
      Updating
    </span>
  );
}
