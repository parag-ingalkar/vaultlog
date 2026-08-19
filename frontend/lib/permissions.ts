import type { OrgRole, UserCapabilities } from "@/lib/api/types";

export function canWriteSecrets(
  capabilities?: Pick<UserCapabilities, "can_write_secrets"> | null,
): boolean {
  return capabilities?.can_write_secrets ?? false;
}

export function canManageGrants(
  capabilities?: Pick<UserCapabilities, "can_create_vaults"> | null,
): boolean {
  return capabilities?.can_create_vaults ?? false;
}

export function canReadAudit(
  capabilities?: Pick<UserCapabilities, "can_read_audit"> | null,
): boolean {
  return capabilities?.can_read_audit ?? false;
}

export function canAccessTeam(
  capabilities?: Pick<
    UserCapabilities,
    "can_manage_members" | "can_manage_invitations"
  > | null,
): boolean {
  return Boolean(
    capabilities?.can_manage_members || capabilities?.can_manage_invitations,
  );
}

export function canInviteRole(
  callerRole: OrgRole | undefined,
  inviteRole: OrgRole,
): boolean {
  if (callerRole === "owner") {
    return inviteRole === "admin" || inviteRole === "member" || inviteRole === "viewer";
  }
  if (callerRole === "admin") {
    return inviteRole === "member" || inviteRole === "viewer";
  }
  return false;
}

export function canRemoveMember(
  callerRole: OrgRole | undefined,
  targetRole: OrgRole,
  targetMembershipId: string,
  selfMembershipId: string | undefined,
): boolean {
  if (!callerRole || !selfMembershipId) return false;
  if (targetMembershipId === selfMembershipId) return false;
  if (targetRole === "owner") return false;
  if (callerRole === "admin" && targetRole === "admin") {
    return false;
  }
  return callerRole === "owner" || callerRole === "admin";
}

export const INVITABLE_ROLES: OrgRole[] = ["admin", "member", "viewer"];

export function invitableRolesFor(callerRole: OrgRole | undefined): OrgRole[] {
  return INVITABLE_ROLES.filter((role) => canInviteRole(callerRole, role));
}
