import { apiRequest } from "@/lib/api/client";
import type { MemberResponse } from "@/lib/api/types";

export async function listMembers(): Promise<MemberResponse[]> {
  return apiRequest<MemberResponse[]>("/members");
}

export async function removeMember(
  membershipId: string,
  stepUpToken: string,
): Promise<void> {
  return apiRequest<void>(`/members/${membershipId}`, {
    method: "DELETE",
    stepUpToken,
  });
}
