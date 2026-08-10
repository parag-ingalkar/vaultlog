import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getVault, listGrants, listVaults } from "./api";

export function useVaultsQuery() {
  return useQuery({
    queryKey: queryKeys.vaults.list(),
    queryFn: listVaults,
  });
}

export function useVaultQuery(vaultId: string) {
  return useQuery({
    queryKey: queryKeys.vaults.detail(vaultId),
    queryFn: () => getVault(vaultId),
    enabled: Boolean(vaultId),
  });
}

export function useVaultGrantsQuery(vaultId: string) {
  return useQuery({
    queryKey: queryKeys.vaults.grants(vaultId),
    queryFn: () => listGrants(vaultId),
    enabled: Boolean(vaultId),
  });
}
