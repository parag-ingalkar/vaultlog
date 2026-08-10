"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";
import {
  useConfirmMfaMutation,
  useEnrollMfaMutation,
} from "@/domains/auth/mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

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

  if (recoveryCodes) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-4 dark:bg-zinc-950">
        <Card className="w-full max-w-lg">
          <h1 className="text-xl font-semibold">Save your recovery codes</h1>
          <p className="mt-2 text-sm text-red-600">
            Store these codes securely. They will not be shown again.
          </p>
          <ul className="mt-4 space-y-1 rounded-lg bg-zinc-100 p-4 font-mono text-sm dark:bg-zinc-800">
            {recoveryCodes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <Button
            className="mt-4 w-full"
            onClick={() => router.replace("/vaults")}
          >
            Continue to VaultLog
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-4 dark:bg-zinc-950">
      <Card className="w-full max-w-lg">
        <h1 className="text-xl font-semibold">Set up two-factor authentication</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Owners must enroll MFA before accessing vaults and team features.
        </p>
        {provisioningUri && (
          <div className="mt-4 rounded-lg bg-zinc-100 p-3 text-xs break-all dark:bg-zinc-800">
            <p className="font-medium text-zinc-700 dark:text-zinc-300">
              Provisioning URI (scan in your authenticator app):
            </p>
            <p className="mt-1 text-zinc-600 dark:text-zinc-400">
              {provisioningUri}
            </p>
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
          />
          {confirm.isError && (
            <p className="text-sm text-red-600">Invalid code. Try again.</p>
          )}
          <Button type="submit" disabled={confirm.isPending} className="w-full">
            {confirm.isPending ? "Confirming…" : "Confirm MFA"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
