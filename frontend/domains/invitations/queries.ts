import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { listInvitations, previewInvitation } from "./api";

export function useInvitationsQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.invitations.list(),
    queryFn: listInvitations,
    staleTime: 60_000,
    enabled,
  });
}

export function useInvitationPreviewQuery(token: string) {
  return useQuery({
    queryKey: queryKeys.invitations.preview(token),
    queryFn: () => previewInvitation(token),
    enabled: Boolean(token),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
