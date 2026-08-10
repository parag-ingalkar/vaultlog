import type { AuditEventResponse } from "@/lib/api/types";
import { formatActor } from "@/domains/audit/format-actor";
import { formatActionLabel, formatEventSummary } from "@/domains/audit/format-event";
import { formatTimestamp } from "@/domains/audit/format-timestamp";

const outcomeStyles: Record<string, string> = {
  success:
    "rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  denied:
    "rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  failure:
    "rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-200",
};

function outcomeClassName(outcome: string): string {
  return (
    outcomeStyles[outcome] ??
    "rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
  );
}

type AuditEventRowProps = {
  event: AuditEventResponse;
};

export function AuditEventRow({ event }: AuditEventRowProps) {
  const summary = formatEventSummary(event);
  const hasDetails =
    event.target_id !== null || Object.keys(event.metadata).length > 0;

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium capitalize">{formatActionLabel(event.action)}</p>
        <span className={outcomeClassName(event.outcome)}>{event.outcome}</span>
      </div>
      <p className="mt-1 text-zinc-500">
        {formatActor(event.actor)} · #{event.sequence} ·{" "}
        {formatTimestamp(event.occurred_at)}
      </p>
      {summary && <p className="mt-1 text-zinc-600 dark:text-zinc-400">{summary}</p>}
      {hasDetails && (
        <details className="mt-2 text-xs text-zinc-500">
          <summary className="cursor-pointer select-none">Technical details</summary>
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
                <dd className="mt-1 overflow-x-auto rounded bg-zinc-100 p-2 font-mono dark:bg-zinc-900">
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
