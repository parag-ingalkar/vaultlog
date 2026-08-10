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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";
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
    <div className="space-y-4">
      <Card>
        <CardHeader title="Members" description="Organization members." />
        <QueryBoundary state={membersState} emptyMessage="No members found.">
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {members.data?.map((member) => (
              <li
                key={member.membership_id}
                className="flex items-center justify-between py-3"
              >
                <div>
                  <p className="font-medium">{member.email}</p>
                  <p className="text-sm text-zinc-500">{member.role}</p>
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
      </Card>

      {capabilities?.can_manage_invitations && (
        <Card>
          <CardHeader
            title="Invitations"
            description="Pending email invitations."
          />
          <form onSubmit={handleInvite} className="mb-4 flex gap-2">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <label className="text-sm">
              Role
              <select
                className="mt-1 rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                value={role}
                onChange={(e) => setRole(e.target.value as OrgRole)}
              >
                <option value="admin">admin</option>
                <option value="member">member</option>
                <option value="viewer">viewer</option>
              </select>
            </label>
            <Button type="submit" className="mt-6" disabled={createInvitation.isPending}>
              Invite
            </Button>
          </form>
          <QueryBoundary
            state={invitationsState}
            emptyMessage="No pending invitations."
          >
            <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {invitations.data?.map((invite) => (
                <li
                  key={invite.id}
                  className="flex items-center justify-between py-3"
                >
                  <div>
                    <p className="font-medium">{invite.email}</p>
                    <p className="text-sm text-zinc-500">
                      {invite.role} · expires {invite.expires_at}
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
