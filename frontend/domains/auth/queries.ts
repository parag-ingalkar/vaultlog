import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getMe } from "./api";

export function useMeQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: getMe,
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}
