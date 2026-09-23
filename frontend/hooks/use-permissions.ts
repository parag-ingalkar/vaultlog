import { useAuth } from "@/domains/auth/auth-provider";
import {
  canAccessTeam,
  canInviteRole,
  canManageGrants,
  canReadAudit,
  canRemoveMember,
  canWriteSecrets,
  invitableRolesFor,
} from "@/lib/permissions";

export function usePermissions() {
  const { me, capabilities } = useAuth();

  return {
    me,
    capabilities,
    canWriteSecrets: canWriteSecrets(capabilities),
    canManageGrants: canManageGrants(capabilities),
    canReadAudit: canReadAudit(capabilities),
    canAccessTeam: canAccessTeam(capabilities),
    invitableRoles: invitableRolesFor(me?.role),
    canInviteRole: (inviteRole: Parameters<typeof canInviteRole>[1]) =>
      canInviteRole(me?.role, inviteRole),
    canRemoveMember: (
      targetRole: Parameters<typeof canRemoveMember>[1],
      targetMembershipId: string,
    ) =>
      canRemoveMember(
        me?.role,
        targetRole,
        targetMembershipId,
        me?.membership_id,
      ),
  };
}
