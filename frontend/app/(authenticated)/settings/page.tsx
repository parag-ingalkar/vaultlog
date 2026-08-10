"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";
import {
  useDisableMfaMutation,
  useLogoutMutation,
} from "@/domains/auth/mutations";
import { useOrganizationQuery } from "@/domains/organization/queries";
import { StepUpModal } from "@/components/step-up-modal";
import { useStepUpHandler } from "@/hooks/use-step-up-handler";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";

export default function SettingsPage() {
  const router = useRouter();
  const { me } = useAuth();
  const org = useOrganizationQuery();
  const logout = useLogoutMutation();
  const disableMfa = useDisableMfaMutation();
  const { stepUpState, clearStepUp, handleStepUpError } = useStepUpHandler();

  const handleLogout = async () => {
    await logout.mutateAsync();
    router.replace("/login");
  };

  const handleDisableMfa = async () => {
    try {
      await disableMfa.mutateAsync();
    } catch (error) {
      handleStepUpError(error, "step-up:manage-mfa", () =>
        disableMfa.mutateAsync(),
      );
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Organization" />
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-zinc-500">Name</dt>
            <dd>{org.data?.name ?? me?.organization.name}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Your role</dt>
            <dd>{me?.role}</dd>
          </div>
        </dl>
      </Card>

      <Card>
        <CardHeader title="Account" />
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-zinc-500">Email</dt>
            <dd>{me?.email}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">MFA</dt>
            <dd>{me?.mfa_enabled ? "Enabled" : "Not enabled"}</dd>
          </div>
        </dl>
        {me?.mfa_enabled && (
          <Button
            variant="danger"
            className="mt-4"
            onClick={handleDisableMfa}
            disabled={disableMfa.isPending}
          >
            Disable MFA
          </Button>
        )}
      </Card>

      <Card>
        <CardHeader title="Session" />
        <Button variant="secondary" onClick={handleLogout}>
          Sign out
        </Button>
      </Card>

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
