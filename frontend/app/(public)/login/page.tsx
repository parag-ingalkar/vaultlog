"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { isApiError } from "@/lib/api/errors";
import { isMfaRequiredResponse } from "@/domains/auth/api";
import {
  useLoginMutation,
  useVerifyMfaMutation,
} from "@/domains/auth/mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const registered = searchParams.get("registered") === "1";
  const login = useLoginMutation();
  const verifyMfa = useVerifyMfaMutation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [challengeToken, setChallengeToken] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await login.mutateAsync({ email, password });
      if (isMfaRequiredResponse(result)) {
        setChallengeToken(result.challenge_token);
        return;
      }
      router.replace("/vaults");
    } catch {
      // error shown below
    }
  };

  const handleMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!challengeToken) return;
    try {
      await verifyMfa.mutateAsync({
        challenge_token: challengeToken,
        code: mfaCode,
      });
      router.replace("/vaults");
    } catch {
      // error shown below
    }
  };

  const error = login.error ?? verifyMfa.error;

  return (
    <Card>
      <h1 className="text-xl font-semibold text-ink">Sign in</h1>
      <p className="mt-1 text-sm text-muted">
        Access your organization&apos;s vaults and secrets.
      </p>

      {registered && (
        <p className="mt-4 rounded-[var(--radius-control)] bg-success-subtle px-3 py-2 text-sm text-success">
          Account created. Sign in to continue.
        </p>
      )}

      {!challengeToken ? (
        <form onSubmit={handleLogin} className="mt-6 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          {error && (
            <p className="text-sm text-danger" role="alert">
              {isApiError(login.error)
                ? "Invalid email or password."
                : "Sign in failed."}
            </p>
          )}
          <Button type="submit" loading={login.isPending} className="w-full">
            Sign in
          </Button>
        </form>
      ) : (
        <form onSubmit={handleMfa} className="mt-6 space-y-4">
          <p className="text-sm text-muted">
            Enter the code from your authenticator app or a recovery code.
          </p>
          <Input
            label="Authentication code"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
            required
            minLength={6}
            autoComplete="one-time-code"
            inputMode="numeric"
          />
          {error && (
            <p className="text-sm text-danger" role="alert">
              Invalid code. Try again.
            </p>
          )}
          <Button type="submit" loading={verifyMfa.isPending} className="w-full">
            Verify
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            onClick={() => {
              setChallengeToken(null);
              setMfaCode("");
            }}
          >
            Back to sign in
          </Button>
        </form>
      )}

      <p className="mt-6 text-center text-sm text-muted">
        New organization?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create one
        </Link>
      </p>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Card><p className="text-sm text-muted">Loading…</p></Card>}>
      <LoginForm />
    </Suspense>
  );
}
