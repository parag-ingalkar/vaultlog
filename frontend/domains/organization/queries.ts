import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getOrganization } from "./api";

export function useOrganizationQuery() {
  return useQuery({
    queryKey: queryKeys.organization.detail(),
    queryFn: getOrganization,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
