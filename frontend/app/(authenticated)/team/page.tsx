"use client";

import { useState } from "react";
import { useAuth } from "@/domains/auth/auth-provider";
import { useMembersQuery } from "@/domains/members/queries";
import { useRemoveMemberMutation } from "@/domains/members/mutations";
import { useInvitationsQuery } from "@/domains/invitations/queries";
import {
  useCreateInvitationMutation,
  useRevokeInvitationMutation,
} from "@/domains/invitations/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StepUpModal } from "@/components/step-up-modal";
import { useStepUpHandler } from "@/hooks/use-step-up-handler";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { OrgRole } from "@/lib/api/types";

export default function TeamPage() {
  const { capabilities } = useAuth();
  const members = useMembersQuery();
  const invitations = useInvitationsQuery();
  const createInvitation = useCreateInvitationMutation();
  const revokeInvitation = useRevokeInvitationMutation();
  const removeMember = useRemoveMemberMutation();
  const { stepUpState, clearStepUp, handleStepUpError } = useStepUpHandler();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>("member");

  const membersState = getQueryState(members);
  const invitationsState = getQueryState(invitations);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    await createInvitation.mutateAsync({ email, role });
    setEmail("");
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
                  {capabilities?.can_manage_members && (
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
              <option value="admin">Admin</option>
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </Select>
            <div className="flex items-end">
              <Button type="submit" loading={createInvitation.isPending}>
                Send invite
              </Button>
            </div>
          </form>

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
                          Expires {new Date(invite.expires_at).toLocaleDateString()}
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
  );
}
