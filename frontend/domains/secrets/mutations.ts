import { useMutation, useQueryClient } from "@tanstack/react-query";
import { withStepUp } from "@/lib/auth/with-step-up";
import { invalidateSecrets } from "@/lib/query/invalidation";
import { queryKeys } from "@/lib/query/keys";
import type {
  RevealResponse,
  RotateSecretRequest,
  SecretCreateRequest,
  SecretMetaResponse,
} from "@/lib/api/types";
import {
  createSecret,
  deleteSecret,
  revealSecret,
  rotateSecret,
} from "./api";

export function useCreateSecretMutation(vaultId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: SecretCreateRequest) => createSecret(vaultId, body),
    onSuccess: (created) => {
      queryClient.setQueryData<SecretMetaResponse[]>(
        queryKeys.secrets.list(vaultId),
        (previous) => [...(previous ?? []), created],
      );
    },
    onSettled: () => invalidateSecrets(queryClient, vaultId),
  });
}

export function useRevealSecretMutation(vaultId: string, secretId: string) {
  return useMutation({
    mutationFn: (version?: number) => revealSecret(vaultId, secretId, version),
    gcTime: 0,
  });
}

export function useRotateSecretMutation(vaultId: string, secretId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: RotateSecretRequest) =>
      rotateSecret(vaultId, secretId, body),
    onMutate: async () => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.secrets.list(vaultId),
      });
      const previous = queryClient.getQueryData<SecretMetaResponse[]>(
        queryKeys.secrets.list(vaultId),
      );
      if (previous) {
        queryClient.setQueryData(
          queryKeys.secrets.list(vaultId),
          previous.map((secret) =>
            secret.id === secretId
              ? {
                  ...secret,
                  current_version: secret.current_version + 1,
                  updated_at: new Date().toISOString(),
                }
              : secret,
          ),
        );
      }
      return { previous };
    },
    onError: (_err, _body, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.secrets.list(vaultId),
          context.previous,
        );
      }
    },
    onSettled: () => invalidateSecrets(queryClient, vaultId),
  });
}

export function useDeleteSecretMutation(vaultId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (secretId: string) =>
      withStepUp("step-up:delete-secret", (token) =>
        deleteSecret(vaultId, secretId, token),
      ),
    onMutate: async (secretId) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.secrets.list(vaultId),
      });
      const previous = queryClient.getQueryData<SecretMetaResponse[]>(
        queryKeys.secrets.list(vaultId),
      );
      queryClient.setQueryData(
        queryKeys.secrets.list(vaultId),
        (previous ?? []).filter((secret) => secret.id !== secretId),
      );
      return { previous };
    },
    onError: (_err, _secretId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.secrets.list(vaultId),
          context.previous,
        );
      }
    },
    onSettled: () => invalidateSecrets(queryClient, vaultId),
  });
}

export type { RevealResponse };
