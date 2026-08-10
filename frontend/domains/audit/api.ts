import { apiRequest } from "@/lib/api/client";
import type { AuditEventResponse, AuditFilters } from "@/lib/api/types";

export async function listAuditEvents(
  filters: AuditFilters = {},
): Promise<AuditEventResponse[]> {
  const params = new URLSearchParams();
  if (filters.action) params.set("action", filters.action);
  if (filters.target_id) params.set("target_id", filters.target_id);
  if (filters.before_sequence !== undefined) {
    params.set("before_sequence", String(filters.before_sequence));
  }
  if (filters.limit !== undefined) {
    params.set("limit", String(filters.limit));
  }

  const query = params.toString();
  const path = query ? `/audit-events?${query}` : "/audit-events";
  return apiRequest<AuditEventResponse[]>(path);
}
