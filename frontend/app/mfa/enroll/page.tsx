"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/domains/auth/auth-provider";
import {
  useConfirmMfaMutation,
  useEnrollMfaMutation,
} from "@/domains/auth/mutations";
import { downloadTextFile } from "@/lib/copy";
import { MfaQrCode } from "@/components/mfa-qr-code";
import { CopyButton } from "@/components/copy-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ListSkeleton } from "@/components/ui/skeleton";

export default function MfaEnrollPage() {
  const router = useRouter();
  const { isAuthenticated, isInitializing, refetchMe } = useAuth();
  const enroll = useEnrollMfaMutation();
  const confirm = useConfirmMfaMutation();
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const enrolledRef = useRef(false);

  useEffect(() => {
    if (isInitializing) return;
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isInitializing, router]);

  useEffect(() => {
    if (enrolledRef.current) return;
    enrolledRef.current = true;
    enroll.mutate(undefined, {
      onSuccess: (data) => setProvisioningUri(data.provisioning_uri),
    });
  }, [enroll]);

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await confirm.mutateAsync(code);
      setRecoveryCodes(result.recovery_codes);
      await refetchMe();
    } catch {
      // shown below
    }
  };

  const recoveryText = recoveryCodes?.join("\n") ?? "";

  if (isInitializing || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-2 p-4">
        <div className="w-full max-w-lg">
          <ListSkeleton rows={4} />
        </div>
      </div>
    );
  }

  if (recoveryCodes) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-2 p-4">
        <Card className="w-full max-w-lg">
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-primary-subtle text-primary">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <h1 className="text-xl font-semibold text-ink">Save your recovery codes</h1>
          <p className="mt-2 text-sm text-muted">
            Store these codes somewhere safe. Each can be used once if you lose
            access to your authenticator.
          </p>
          <ul className="mt-4 space-y-1 rounded-[var(--radius-panel)] bg-surface-2 p-4 font-mono text-sm text-ink">
            {recoveryCodes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            <CopyButton value={recoveryText} label="Copy all" />
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                downloadTextFile("vaultlog-recovery-codes.txt", recoveryText)
              }
            >
              Download
            </Button>
          </div>
          <Button
            className="mt-6 w-full"
            onClick={() => router.replace("/vaults")}
          >
            Continue to VaultLog
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-2 p-4">
      <Card className="w-full max-w-lg">
        <h1 className="text-xl font-semibold text-ink">
          Set up two-factor authentication
        </h1>
        <p className="mt-2 text-sm text-muted">
          Owners must enroll MFA before accessing vaults and team features.
        </p>

        {enroll.isPending && !provisioningUri && (
          <div className="mt-6">
            <ListSkeleton rows={3} />
          </div>
        )}

        {provisioningUri && (
          <div className="mt-6">
            <MfaQrCode uri={provisioningUri} />
          </div>
        )}

        <form onSubmit={handleConfirm} className="mt-6 space-y-4">
          <Input
            label="6-digit code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            minLength={6}
            maxLength={8}
            autoComplete="one-time-code"
            inputMode="numeric"
            hint="Enter the code shown in your authenticator app"
          />
          {confirm.isError && (
            <p className="text-sm text-danger" role="alert">
              Invalid code. Try again.
            </p>
          )}
          <Button
            type="submit"
            loading={confirm.isPending}
            className="w-full"
            disabled={!provisioningUri}
          >
            Confirm MFA
          </Button>
        </form>
      </Card>
    </div>
  );
}
