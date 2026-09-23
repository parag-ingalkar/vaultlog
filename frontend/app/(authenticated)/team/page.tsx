"use client";

import { useState } from "react";
import { useMembersQuery } from "@/domains/members/queries";
import { useRemoveMemberMutation } from "@/domains/members/mutations";
import { useInvitationsQuery } from "@/domains/invitations/queries";
import {
  useCreateInvitationMutation,
  useRevokeInvitationMutation,
} from "@/domains/invitations/mutations";
import { CapabilityGuard } from "@/components/capability-guard";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StepUpModal } from "@/components/step-up-modal";
import { useStepUpHandler } from "@/hooks/use-step-up-handler";
import { usePermissions } from "@/hooks/use-permissions";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MutationError } from "@/components/mutation-error";
import type { OrgRole } from "@/lib/api/types";

export default function TeamPage() {
  const {
    capabilities,
    canAccessTeam,
    canRemoveMember,
    invitableRoles,
  } = usePermissions();
  const members = useMembersQuery(canAccessTeam);
  const invitations = useInvitationsQuery(
    Boolean(capabilities?.can_manage_invitations),
  );
  const createInvitation = useCreateInvitationMutation();
  const revokeInvitation = useRevokeInvitationMutation();
  const removeMember = useRemoveMemberMutation();
  const { stepUpState, clearStepUp, handleStepUpError } = useStepUpHandler();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>(
    invitableRoles.includes("member") ? "member" : invitableRoles[0] ?? "member",
  );

  const membersState = getQueryState(members);
  const invitationsState = getQueryState(invitations);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createInvitation.mutateAsync({ email, role });
      setEmail("");
    } catch {
      // shown via MutationError
    }
  };

  const handleRemoveMember = async (membershipId: string) => {
    try {
      await removeMember.mutateAsync(membershipId);
    } catch (error) {
      handleStepUpError(error, "step-up:remove-member", () =>
        removeMember.mutateAsync(membershipId),
      );
    }
  };

  return (
    <CapabilityGuard allowed={canAccessTeam}>
      <div className="space-y-6">
        <PageHeader
          title="Team"
          description="Manage members and invitations for your organization."
        />

        <Card>
          <h2 className="text-lg font-semibold text-ink">Members</h2>
          <div className="mt-4">
            <QueryBoundary state={membersState} emptyMessage="No members found">
              <ul className="divide-y divide-border">
                {members.data?.map((member) => (
                  <li
                    key={member.membership_id}
                    className="flex flex-wrap items-center justify-between gap-3 py-4"
                  >
                    <div>
                      <p className="font-medium text-ink">{member.email}</p>
                      <p className="mt-0.5">
                        <Badge variant="muted">{member.role}</Badge>
                      </p>
                    </div>
                    {canRemoveMember(member.role, member.membership_id) && (
                      <Button
                        variant="ghost"
                        onClick={() => handleRemoveMember(member.membership_id)}
                      >
                        Remove
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </QueryBoundary>
          </div>
        </Card>

        {capabilities?.can_manage_invitations && (
          <Card>
            <h2 className="text-lg font-semibold text-ink">Invitations</h2>
            <p className="mt-1 text-sm text-muted">
              Invite teammates by email. They&apos;ll receive a link to join.
            </p>

            <form
              onSubmit={handleInvite}
              className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]"
            >
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <Select
                label="Role"
                value={role}
                onChange={(e) => setRole(e.target.value as OrgRole)}
              >
                {invitableRoles.map((inviteRole) => (
                  <option key={inviteRole} value={inviteRole}>
                    {inviteRole.charAt(0).toUpperCase() + inviteRole.slice(1)}
                  </option>
                ))}
              </Select>
              <div className="flex items-end">
                <Button type="submit" loading={createInvitation.isPending}>
                  Send invite
                </Button>
              </div>
            </form>
            <div className="mt-3">
              <MutationError error={createInvitation.error} />
            </div>

            <div className="mt-6">
              <QueryBoundary
                state={invitationsState}
                emptyMessage="No pending invitations"
              >
                <ul className="divide-y divide-border">
                  {invitations.data?.map((invite) => (
                    <li
                      key={invite.id}
                      className="flex flex-wrap items-center justify-between gap-3 py-4"
                    >
                      <div>
                        <p className="font-medium text-ink">{invite.email}</p>
                        <p className="mt-0.5 text-sm text-muted">
                          <Badge variant="default">{invite.role}</Badge>
                          <span className="ml-2">
                            Expires{" "}
                            {new Date(invite.expires_at).toLocaleDateString()}
                          </span>
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        onClick={() => revokeInvitation.mutate(invite.id)}
                      >
                        Revoke
                      </Button>
                    </li>
                  ))}
                </ul>
              </QueryBoundary>
            </div>
          </Card>
        )}

        {stepUpState && (
          <StepUpModal
            purpose={stepUpState.purpose}
            open
            onClose={clearStepUp}
            onSuccess={stepUpState.retry}
          />
        )}
      </div>
    </CapabilityGuard>
  );
}
