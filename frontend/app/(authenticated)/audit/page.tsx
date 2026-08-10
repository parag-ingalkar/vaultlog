"use client";

import { useState } from "react";
import { AuditEventRow } from "@/domains/audit/audit-event-row";
import { useAuditEventsInfiniteQuery } from "@/domains/audit/queries";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";

export default function AuditPage() {
  const [action, setAction] = useState("");
  const audit = useAuditEventsInfiniteQuery({
    action: action || undefined,
    limit: 50,
  });

  const allEvents = audit.data?.pages.flat() ?? [];
  const state = getQueryState({
    ...audit,
    data: allEvents,
    isSuccess: audit.isSuccess,
    isPending: audit.isPending,
    isFetching: audit.isFetching,
    isStale: audit.isStale,
    isError: audit.isError,
    error: audit.error,
  });

  return (
    <Card>
      <CardHeader
        title="Audit log"
        description="Append-only security ledger for your organization."
      />
      <form
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          audit.refetch();
        }}
      >
        <Input
          label="Filter by action"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="e.g. secret.revealed"
        />
        <Button type="submit" variant="secondary" className="mt-6">
          Apply filter
        </Button>
      </form>

      <QueryBoundary state={state} emptyMessage="No audit events yet.">
        <ul className="divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
          {allEvents.map((event) => (
            <AuditEventRow key={event.id} event={event} />
          ))}
        </ul>
        {audit.hasNextPage && (
          <Button
            className="mt-4"
            variant="secondary"
            onClick={() => audit.fetchNextPage()}
            disabled={audit.isFetchingNextPage}
          >
            {audit.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        )}
      </QueryBoundary>
    </Card>
  );
}
