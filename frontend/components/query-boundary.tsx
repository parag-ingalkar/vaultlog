import type { ReactNode } from "react";
import { getQueryState, type QueryStateView } from "@/lib/query/query-state";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Inbox } from "lucide-react";

type QueryBoundaryProps = {
  state: QueryStateView;
  children: ReactNode;
  emptyMessage?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  loadingRows?: number;
};

export function QueryBoundary({
  state,
  children,
  emptyMessage = "Nothing here yet",
  emptyDescription,
  emptyAction,
  loadingRows = 4,
}: QueryBoundaryProps) {
  if (state.isInitialLoading) {
    return <ListSkeleton rows={loadingRows} />;
  }

  if (state.isError) {
    return (
      <div
        className="rounded-[var(--radius-panel)] border border-danger/30 bg-danger-subtle px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {state.error?.message ?? "Something went wrong."}
        {state.isRateLimited && state.retryAfter && (
          <span className="mt-1 block">
            Try again in {state.retryAfter} seconds.
          </span>
        )}
      </div>
    );
  }

  if (state.isEmpty) {
    return (
      <EmptyState
        icon={Inbox}
        title={emptyMessage}
        description={emptyDescription}
        action={emptyAction}
      />
    );
  }

  return <>{children}</>;
}

export { getQueryState };
