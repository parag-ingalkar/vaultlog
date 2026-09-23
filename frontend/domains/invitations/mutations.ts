import { useMutation, useQueryClient } from "@tanstack/react-query";
import { invalidateInvitations } from "@/lib/query/invalidation";
import { queryKeys } from "@/lib/query/keys";
import type {
  AcceptInvitationRequest,
  InvitationCreateRequest,
  InvitationResponse,
} from "@/lib/api/types";
import {
  acceptInvitation,
  createInvitation,
  revokeInvitation,
} from "./api";

export function useCreateInvitationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: InvitationCreateRequest) => createInvitation(body),
    onSettled: () => invalidateInvitations(queryClient),
  });
}

export function useRevokeInvitationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (invitationId: string) => revokeInvitation(invitationId),
    onMutate: async (invitationId) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.invitations.list(),
      });
      const previous = queryClient.getQueryData<InvitationResponse[]>(
        queryKeys.invitations.list(),
      );
      queryClient.setQueryData(
        queryKeys.invitations.list(),
        (previous ?? []).filter((invite) => invite.id !== invitationId),
      );
      return { previous };
    },
    onError: (_err, _invitationId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.invitations.list(),
          context.previous,
        );
      }
    },
    onSettled: () => invalidateInvitations(queryClient),
  });
}

export function useAcceptInvitationMutation() {
  return useMutation({
    mutationFn: (body: AcceptInvitationRequest) => acceptInvitation(body),
  });
}
