import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { listMembers } from "./api";

export function useMembersQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.members.list(),
    queryFn: listMembers,
    staleTime: 60_000,
    enabled,
  });
}
