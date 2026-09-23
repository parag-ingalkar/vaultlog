import { apiRequest } from "@/lib/api/client";
import type {
  RevealResponse,
  RotateSecretRequest,
  SecretCreateRequest,
  SecretMetaResponse,
} from "@/lib/api/types";

export async function listSecrets(vaultId: string): Promise<SecretMetaResponse[]> {
  return apiRequest<SecretMetaResponse[]>(`/vaults/${vaultId}/secrets`);
}

export async function createSecret(
  vaultId: string,
  body: SecretCreateRequest,
): Promise<SecretMetaResponse> {
  return apiRequest<SecretMetaResponse>(`/vaults/${vaultId}/secrets`, {
    method: "POST",
    body,
  });
}

export async function revealSecret(
  vaultId: string,
  secretId: string,
  version?: number,
): Promise<RevealResponse> {
  const query = version !== undefined ? `?version=${version}` : "";
  return apiRequest<RevealResponse>(
    `/vaults/${vaultId}/secrets/${secretId}/reveal${query}`,
    { method: "POST" },
  );
}

export async function rotateSecret(
  vaultId: string,
  secretId: string,
  body: RotateSecretRequest,
): Promise<SecretMetaResponse> {
  return apiRequest<SecretMetaResponse>(
    `/vaults/${vaultId}/secrets/${secretId}/rotate`,
    { method: "POST", body },
  );
}

export async function deleteSecret(
  vaultId: string,
  secretId: string,
  stepUpToken: string,
): Promise<void> {
  return apiRequest<void>(`/vaults/${vaultId}/secrets/${secretId}`, {
    method: "DELETE",
    stepUpToken,
  });
}
