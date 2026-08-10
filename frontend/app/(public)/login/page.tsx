"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { isMfaRequiredResponse } from "@/domains/auth/api";
import {
  useLoginMutation,
  useVerifyMfaMutation,
} from "@/domains/auth/mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
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

  const error =
    login.error ?? verifyMfa.error
      ? (login.error ?? verifyMfa.error) instanceof Error
        ? (login.error ?? verifyMfa.error)?.message
        : "Sign in failed"
      : null;

  return (
    <Card>
      <h1 className="text-xl font-semibold">Sign in to VaultLog</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Access your organization&apos;s vaults and secrets.
      </p>

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
            <p className="text-sm text-red-600">
              {isApiError(login.error)
                ? "Invalid email or password."
                : error}
            </p>
          )}
          <Button type="submit" disabled={login.isPending} className="w-full">
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      ) : (
        <form onSubmit={handleMfa} className="mt-6 space-y-4">
          <p className="text-sm text-zinc-500">
            Enter your authenticator code or recovery code.
          </p>
          <Input
            label="MFA code"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
            required
            minLength={6}
            autoComplete="one-time-code"
          />
          {error && (
            <p className="text-sm text-red-600">Invalid code. Try again.</p>
          )}
          <Button type="submit" disabled={verifyMfa.isPending} className="w-full">
            {verifyMfa.isPending ? "Verifying…" : "Verify"}
          </Button>
        </form>
      )}

      <p className="mt-4 text-center text-sm text-zinc-500">
        New organization?{" "}
        <Link href="/register" className="text-emerald-600 hover:underline">
          Register
        </Link>
      </p>
    </Card>
  );
}
