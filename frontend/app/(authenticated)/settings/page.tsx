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
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Organization details and account security."
      />

      <Card>
        <h2 className="text-sm font-medium text-ink">Organization</h2>
        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="text-muted">Name</dt>
            <dd className="mt-1 font-medium text-ink">
              {org.data?.name ?? me?.organization.name}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Your role</dt>
            <dd className="mt-1">
              <Badge variant="muted">{me?.role}</Badge>
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <h2 className="text-sm font-medium text-ink">Account</h2>
        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="text-muted">Email</dt>
            <dd className="mt-1 font-medium text-ink">{me?.email}</dd>
          </div>
          <div>
            <dt className="text-muted">Two-factor authentication</dt>
            <dd className="mt-1">
              <Badge variant={me?.mfa_enabled ? "success" : "muted"}>
                {me?.mfa_enabled ? "Enabled" : "Not enabled"}
              </Badge>
            </dd>
          </div>
        </dl>
        {me?.mfa_enabled && (
          <Button
            variant="danger"
            className="mt-6"
            onClick={handleDisableMfa}
            loading={disableMfa.isPending}
          >
            Disable MFA
          </Button>
        )}
      </Card>

      <Card>
        <h2 className="text-sm font-medium text-ink">Session</h2>
        <p className="mt-1 text-sm text-muted">
          Sign out on this device. Your refresh token will be cleared.
        </p>
        <Button
          variant="secondary"
          className="mt-4"
          onClick={handleLogout}
          loading={logout.isPending}
        >
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
