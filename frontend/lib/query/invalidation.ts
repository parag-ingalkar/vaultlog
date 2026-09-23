import type { QueryClient } from "@tanstack/react-query";
import { getMe } from "@/domains/auth/api";
import { queryKeys } from "./keys";

export async function invalidateSession(queryClient: QueryClient): Promise<void> {
  await queryClient.fetchQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: getMe,
  });
}

export function invalidateOrganization(queryClient: QueryClient): void {
  queryClient.invalidateQueries({
    queryKey: queryKeys.organization.detail(),
  });
}

export function invalidateVaults(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.vaults.lists() });
}

export function invalidateVault(
  queryClient: QueryClient,
  vaultId: string,
): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.vaults.list() });
  queryClient.invalidateQueries({ queryKey: queryKeys.vaults.detail(vaultId) });
}

export function removeVaultDetail(
  queryClient: QueryClient,
  vaultId: string,
): void {
  queryClient.removeQueries({ queryKey: queryKeys.vaults.detail(vaultId) });
}

export function invalidateSecrets(
  queryClient: QueryClient,
  vaultId: string,
): void {
  queryClient.invalidateQueries({
    queryKey: queryKeys.secrets.list(vaultId),
  });
}

export function invalidateVaultGrants(
  queryClient: QueryClient,
  vaultId: string,
): void {
  queryClient.invalidateQueries({
    queryKey: queryKeys.vaults.grants(vaultId),
  });
}

export function invalidateMembers(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.members.list() });
}

export function invalidateInvitations(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.invitations.list() });
}

export function invalidateAudit(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.audit.lists() });
}
