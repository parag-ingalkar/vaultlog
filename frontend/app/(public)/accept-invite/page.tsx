"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { fieldErrorsFromApi } from "@/lib/form-errors";
import { useInvitationPreviewQuery } from "@/domains/invitations/queries";
import { useAcceptInvitationMutation } from "@/domains/invitations/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const preview = useInvitationPreviewQuery(token);
  const accept = useAcceptInvitationMutation();
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);

  const state = getQueryState(preview);
  const fieldErrors = isApiError(accept.error)
    ? fieldErrorsFromApi(accept.error.fields)
    : {};

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
        <h1 className="text-xl font-semibold text-ink">Invalid invitation link</h1>
        <p className="mt-2 text-sm text-muted">
          This link is missing a token. Check your email for the correct link.
        </p>
      </Card>
    );
  }

  if (accepted) {
    return (
      <Card>
        <h1 className="text-xl font-semibold text-ink">You&apos;re all set</h1>
        <p className="mt-2 text-sm text-muted">
          Your account is ready. Sign in to access your organization.
        </p>
        <Link href="/login" className="mt-6 block">
          <Button className="w-full">Go to sign in</Button>
        </Link>
      </Card>
    );
  }

  return (
    <Card>
      <QueryBoundary state={state} loadingRows={3}>
        {preview.data && (
          <>
            <h1 className="text-xl font-semibold text-ink">
              Join {preview.data.organization_name}
            </h1>
            <p className="mt-2 text-sm text-muted">
              You&apos;ve been invited as{" "}
              <Badge variant="default">{preview.data.role}</Badge> for{" "}
              {preview.data.email_masked}.
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
                hint="At least 12 characters"
                error={fieldErrors.password}
              />
              {accept.isError && !fieldErrors.password && (
                <p className="text-sm text-danger" role="alert">
                  {isApiError(accept.error)
                    ? "Could not accept invitation. Check your password."
                    : "Accept failed."}
                </p>
              )}
              <Button
                type="submit"
                loading={accept.isPending}
                className="w-full"
              >
                Accept invitation
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
          <p className="text-sm text-muted">Loading invitation…</p>
        </Card>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}
