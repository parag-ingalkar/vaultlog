import { apiRequest } from "@/lib/api/client";
import type {
  AcceptInvitationRequest,
  InvitationCreateRequest,
  InvitationPreviewResponse,
  InvitationResponse,
} from "@/lib/api/types";

export async function listInvitations(): Promise<InvitationResponse[]> {
  return apiRequest<InvitationResponse[]>("/invitations");
}

export async function createInvitation(
  body: InvitationCreateRequest,
): Promise<InvitationResponse> {
  return apiRequest<InvitationResponse>("/invitations", {
    method: "POST",
    body,
  });
}

export async function revokeInvitation(invitationId: string): Promise<void> {
  return apiRequest<void>(`/invitations/${invitationId}`, {
    method: "DELETE",
  });
}

export async function previewInvitation(
  token: string,
): Promise<InvitationPreviewResponse> {
  return apiRequest<InvitationPreviewResponse>(
    `/invitations/preview?token=${encodeURIComponent(token)}`,
    { skipAuth: true },
  );
}

export async function acceptInvitation(
  body: AcceptInvitationRequest,
): Promise<void> {
  return apiRequest<void>("/invitations/accept", {
    method: "POST",
    body,
    skipAuth: true,
  });
}
