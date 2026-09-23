import { useMutation, useQueryClient } from "@tanstack/react-query";
import { withStepUp } from "@/lib/auth/with-step-up";
import {
  invalidateVault,
  invalidateVaultGrants,
  invalidateVaults,
  removeVaultDetail,
} from "@/lib/query/invalidation";
import { queryKeys } from "@/lib/query/keys";
import type {
  GrantRequest,
  VaultCreateRequest,
  VaultResponse,
  VaultUpdateRequest,
} from "@/lib/api/types";
import {
  createVault,
  deleteVault,
  revokeGrant,
  updateVault,
  upsertGrant,
} from "./api";

export function useCreateVaultMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: VaultCreateRequest) => createVault(body),
    onSuccess: (created) => {
      queryClient.setQueryData<VaultResponse[]>(
        queryKeys.vaults.list(),
        (previous) => [...(previous ?? []), created],
      );
    },
    onSettled: () => invalidateVaults(queryClient),
  });
}

export function useUpdateVaultMutation(vaultId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: VaultUpdateRequest) => updateVault(vaultId, body),
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.vaults.list() });
      await queryClient.cancelQueries({
        queryKey: queryKeys.vaults.detail(vaultId),
      });

      const previousList = queryClient.getQueryData<VaultResponse[]>(
        queryKeys.vaults.list(),
      );
      const previousDetail = queryClient.getQueryData<VaultResponse>(
        queryKeys.vaults.detail(vaultId),
      );

      if (previousList) {
        queryClient.setQueryData(
          queryKeys.vaults.list(),
          previousList.map((v) =>
            v.id === vaultId ? { ...v, ...body } : v,
          ),
        );
      }
      if (previousDetail) {
        queryClient.setQueryData(queryKeys.vaults.detail(vaultId), {
          ...previousDetail,
          ...body,
        });
      }

      return { previousList, previousDetail };
    },
    onError: (_err, _body, context) => {
      if (context?.previousList) {
        queryClient.setQueryData(queryKeys.vaults.list(), context.previousList);
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(
          queryKeys.vaults.detail(vaultId),
          context.previousDetail,
        );
      }
    },
    onSettled: () => invalidateVault(queryClient, vaultId),
  });
}

export function useDeleteVaultMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (vaultId: string) =>
      withStepUp("step-up:delete-vault", (token) => deleteVault(vaultId, token)),
    onMutate: async (vaultId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.vaults.list() });
      const previous = queryClient.getQueryData<VaultResponse[]>(
        queryKeys.vaults.list(),
      );
      queryClient.setQueryData(
        queryKeys.vaults.list(),
        (previous ?? []).filter((vault) => vault.id !== vaultId),
      );
      removeVaultDetail(queryClient, vaultId);
      return { previous };
    },
    onError: (_err, _vaultId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.vaults.list(), context.previous);
      }
    },
    onSettled: () => invalidateVaults(queryClient),
  });
}

export function useUpsertGrantMutation(vaultId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: GrantRequest) => upsertGrant(vaultId, body),
    onSettled: () => invalidateVaultGrants(queryClient, vaultId),
  });
}

export function useRevokeGrantMutation(vaultId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (membershipId: string) => revokeGrant(vaultId, membershipId),
    onSettled: () => invalidateVaultGrants(queryClient, vaultId),
  });
}
