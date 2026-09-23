import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { enrollMfa, getMe } from "./api";

export function useMeQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: getMe,
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useMfaEnrollQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.auth.mfaEnroll(),
    queryFn: enrollMfa,
    enabled,
    staleTime: Infinity,
    retry: 1,
  });
}
