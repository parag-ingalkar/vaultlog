"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { useInvitationPreviewQuery } from "@/domains/invitations/queries";
import { useAcceptInvitationMutation } from "@/domains/invitations/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const preview = useInvitationPreviewQuery(token);
  const accept = useAcceptInvitationMutation();
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);

  const state = getQueryState(preview);

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await accept.mutateAsync({ token, password });
      setAccepted(true);
    } catch {
      // shown below
    }
  };

  if (!token) {
    return (
      <Card>
        <h1 className="text-xl font-semibold">Invalid invitation link</h1>
        <p className="mt-2 text-sm text-zinc-500">
          This link is missing a token. Check your email for the correct link.
        </p>
      </Card>
    );
  }

  if (accepted) {
    return (
      <Card>
        <h1 className="text-xl font-semibold">Invitation accepted</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Your account is ready. Sign in to access your organization.
        </p>
        <Link href="/login" className="mt-4 inline-block text-emerald-600">
          Go to sign in
        </Link>
      </Card>
    );
  }

  return (
    <Card>
      <QueryBoundary state={state} loadingMessage="Loading invitation…">
        {preview.data && (
          <>
            <h1 className="text-xl font-semibold">
              Join {preview.data.organization_name}
            </h1>
            <p className="mt-2 text-sm text-zinc-500">
              You&apos;ve been invited as <strong>{preview.data.role}</strong>{" "}
              for {preview.data.email_masked}.
            </p>
            <form onSubmit={handleAccept} className="mt-6 space-y-4">
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={12}
                maxLength={128}
              />
              {accept.isError && (
                <p className="text-sm text-red-600">
                  {isApiError(accept.error)
                    ? "Could not accept invitation. Check your password."
                    : "Accept failed."}
                </p>
              )}
              <Button
                type="submit"
                disabled={accept.isPending}
                className="w-full"
              >
                {accept.isPending ? "Accepting…" : "Accept invitation"}
              </Button>
            </form>
          </>
        )}
      </QueryBoundary>
    </Card>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <Card>
          <p className="text-sm text-zinc-500">Loading invitation…</p>
        </Card>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}
