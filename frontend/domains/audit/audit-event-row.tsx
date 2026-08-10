import type { AuditEventResponse } from "@/lib/api/types";
import { formatActor } from "@/domains/audit/format-actor";
import { formatActionLabel, formatEventSummary } from "@/domains/audit/format-event";
import { formatTimestamp } from "@/domains/audit/format-timestamp";
import { Badge } from "@/components/ui/badge";

function outcomeVariant(
  outcome: string,
): "success" | "warning" | "danger" | "muted" {
  if (outcome === "success") return "success";
  if (outcome === "denied") return "warning";
  if (outcome === "failure") return "danger";
  return "muted";
}

type AuditEventRowProps = {
  event: AuditEventResponse;
};

export function AuditEventRow({ event }: AuditEventRowProps) {
  const summary = formatEventSummary(event);
  const hasDetails =
    event.target_id !== null || Object.keys(event.metadata).length > 0;

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium text-ink">{formatActionLabel(event.action)}</p>
        <Badge variant={outcomeVariant(event.outcome)}>{event.outcome}</Badge>
      </div>
      <p className="mt-1 text-sm text-muted">
        {formatActor(event.actor)} · #{event.sequence} ·{" "}
        {formatTimestamp(event.occurred_at)}
      </p>
      {summary && <p className="mt-1 text-sm text-ink">{summary}</p>}
      {hasDetails && (
        <details className="mt-2 text-xs text-muted">
          <summary className="cursor-pointer select-none text-primary">
            Technical details
          </summary>
          <dl className="mt-2 space-y-1">
            {event.target_id && (
              <div>
                <dt className="inline font-medium">Target ID: </dt>
                <dd className="inline font-mono">{event.target_id}</dd>
              </div>
            )}
            {event.session_id && (
              <div>
                <dt className="inline font-medium">Session ID: </dt>
                <dd className="inline font-mono">{event.session_id}</dd>
              </div>
            )}
            {Object.keys(event.metadata).length > 0 && (
              <div>
                <dt className="font-medium">Metadata</dt>
                <dd className="mt-1 overflow-x-auto rounded-[var(--radius-control)] bg-surface-2 p-2 font-mono">
                  <pre>{JSON.stringify(event.metadata, null, 2)}</pre>
                </dd>
              </div>
            )}
          </dl>
        </details>
      )}
    </li>
  );
}
