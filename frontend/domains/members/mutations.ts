import { useMutation, useQueryClient } from "@tanstack/react-query";
import { withStepUp } from "@/lib/auth/with-step-up";
import { invalidateMembers } from "@/lib/query/invalidation";
import { queryKeys } from "@/lib/query/keys";
import type { MemberResponse } from "@/lib/api/types";
import { removeMember } from "./api";

export function useRemoveMemberMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (membershipId: string) =>
      withStepUp("step-up:remove-member", (token) =>
        removeMember(membershipId, token),
      ),
    onMutate: async (membershipId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.members.list() });
      const previous = queryClient.getQueryData<MemberResponse[]>(
        queryKeys.members.list(),
      );
      queryClient.setQueryData(
        queryKeys.members.list(),
        (previous ?? []).filter(
          (member) => member.membership_id !== membershipId,
        ),
      );
      return { previous };
    },
    onError: (_err, _membershipId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.members.list(), context.previous);
      }
    },
    onSettled: () => invalidateMembers(queryClient),
  });
}
