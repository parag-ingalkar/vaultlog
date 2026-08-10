import { apiRequest } from "@/lib/api/client";
import type {
  GrantRequest,
  GrantResponse,
  VaultCreateRequest,
  VaultResponse,
  VaultUpdateRequest,
} from "@/lib/api/types";

export async function listVaults(): Promise<VaultResponse[]> {
  return apiRequest<VaultResponse[]>("/vaults");
}

export async function getVault(vaultId: string): Promise<VaultResponse> {
  return apiRequest<VaultResponse>(`/vaults/${vaultId}`);
}

export async function createVault(
  body: VaultCreateRequest,
): Promise<VaultResponse> {
  return apiRequest<VaultResponse>("/vaults", { method: "POST", body });
}

export async function updateVault(
  vaultId: string,
  body: VaultUpdateRequest,
): Promise<VaultResponse> {
  return apiRequest<VaultResponse>(`/vaults/${vaultId}`, {
    method: "PATCH",
    body,
  });
}

export async function deleteVault(
  vaultId: string,
  stepUpToken: string,
): Promise<void> {
  return apiRequest<void>(`/vaults/${vaultId}`, {
    method: "DELETE",
    stepUpToken,
  });
}

export async function listGrants(vaultId: string): Promise<GrantResponse[]> {
  return apiRequest<GrantResponse[]>(`/vaults/${vaultId}/grants`);
}

export async function upsertGrant(
  vaultId: string,
  body: GrantRequest,
): Promise<void> {
  return apiRequest<void>(`/vaults/${vaultId}/grants`, {
    method: "POST",
    body,
  });
}

export async function revokeGrant(
  vaultId: string,
  membershipId: string,
): Promise<void> {
  return apiRequest<void>(`/vaults/${vaultId}/grants/${membershipId}`, {
    method: "DELETE",
  });
}
