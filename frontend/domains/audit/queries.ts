import { useInfiniteQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import type { AuditEventResponse, AuditFilters } from "@/lib/api/types";
import { listAuditEvents } from "./api";

const DEFAULT_LIMIT = 100;

export function useAuditEventsInfiniteQuery(
  filters: Omit<AuditFilters, "before_sequence"> = {},
  enabled = true,
) {
  const limit = filters.limit ?? DEFAULT_LIMIT;

  return useInfiniteQuery({
    queryKey: queryKeys.audit.list({ ...filters, limit }),
    queryFn: ({ pageParam }) =>
      listAuditEvents({
        ...filters,
        limit,
        before_sequence: pageParam,
      }),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage: AuditEventResponse[]) => {
      if (lastPage.length < limit) return undefined;
      const lowestSequence = Math.min(...lastPage.map((e) => e.sequence));
      return lowestSequence;
    },
    staleTime: 0,
    refetchOnWindowFocus: false,
    enabled,
  });
}
