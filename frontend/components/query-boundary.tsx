import type { ReactNode } from "react";
import { getQueryState, type QueryStateView } from "@/lib/query/query-state";

type QueryBoundaryProps = {
  state: QueryStateView;
  children: ReactNode;
  emptyMessage?: string;
  loadingMessage?: string;
};

export function QueryBoundary({
  state,
  children,
  emptyMessage = "No items found.",
  loadingMessage = "Loading…",
}: QueryBoundaryProps) {
  if (state.isInitialLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-zinc-500">
        {loadingMessage}
      </div>
    );
  }

  if (state.isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
        {state.error?.message ?? "Something went wrong."}
        {state.isRateLimited && state.retryAfter && (
          <span className="mt-1 block">
            Retry in {state.retryAfter} seconds.
          </span>
        )}
      </div>
    );
  }

  if (state.isEmpty) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-300 px-4 py-12 text-center text-sm text-zinc-500 dark:border-zinc-700">
        {emptyMessage}
      </div>
    );
  }

  return <>{children}</>;
}

export { getQueryState };
