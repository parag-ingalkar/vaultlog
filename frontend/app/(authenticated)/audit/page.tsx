"use client";

import { useState } from "react";
import { AuditEventRow } from "@/domains/audit/audit-event-row";
import { useAuditEventsInfiniteQuery } from "@/domains/audit/queries";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

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
    <div>
      <PageHeader
        title="Audit log"
        description="A chronological record of security-relevant activity in your organization."
      />

      <Card>
        <form
          className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            audit.refetch();
          }}
        >
          <div className="flex-1">
            <Input
              label="Filter by action"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="e.g. secret.revealed"
            />
          </div>
          <Button type="submit" variant="secondary">
            Apply filter
          </Button>
        </form>

        <QueryBoundary state={state} emptyMessage="No audit events yet">
          <ul className="divide-y divide-border">
            {allEvents.map((event) => (
              <AuditEventRow key={event.id} event={event} />
            ))}
          </ul>
          {audit.hasNextPage && (
            <Button
              className="mt-6"
              variant="secondary"
              onClick={() => audit.fetchNextPage()}
              loading={audit.isFetchingNextPage}
            >
              Load more
            </Button>
          )}
        </QueryBoundary>
      </Card>
    </div>
  );
}
