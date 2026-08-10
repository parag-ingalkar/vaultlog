"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { useAuth } from "@/domains/auth/auth-provider";
import { useSecretsQuery } from "@/domains/secrets/queries";
import {
  useDeleteSecretMutation,
  useRevealSecretMutation,
  useRotateSecretMutation,
} from "@/domains/secrets/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StepUpModal } from "@/components/step-up-modal";
import { useStepUpHandler } from "@/hooks/use-step-up-handler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";

export default function SecretDetailPage() {
  const params = useParams<{ vaultId: string; secretId: string }>();
  const vaultId = params.vaultId;
  const secretId = params.secretId;
  const router = useRouter();
  const { me } = useAuth();
  const secrets = useSecretsQuery(vaultId);
  const reveal = useRevealSecretMutation(vaultId, secretId);
  const rotate = useRotateSecretMutation(vaultId, secretId);
  const deleteSecret = useDeleteSecretMutation(vaultId);
  const { stepUpState, clearStepUp, handleStepUpError } = useStepUpHandler();

  const [revealedValue, setRevealedValue] = useState<string | null>(null);
  const [newValue, setNewValue] = useState("");
  const secret = secrets.data?.find((s) => s.id === secretId);
  const state = getQueryState(secrets);

  useEffect(() => {
    return () => setRevealedValue(null);
  }, []);

  const canModify = me?.role !== "viewer";

  const handleReveal = async () => {
    try {
      const result = await reveal.mutateAsync(undefined);
      setRevealedValue(result.value);
    } catch (error) {
      if (isApiError(error) && error.isRateLimited()) return;
    }
  };

  const handleRotate = async (e: React.FormEvent) => {
    e.preventDefault();
    await rotate.mutateAsync({ value: newValue });
    setNewValue("");
    setRevealedValue(null);
  };

  const handleDelete = async () => {
    try {
      await deleteSecret.mutateAsync(secretId);
      router.push(`/vaults/${vaultId}`);
    } catch (error) {
      handleStepUpError(error, "step-up:delete-secret", () =>
        deleteSecret.mutateAsync(secretId),
      );
    }
  };

  return (
    <div className="space-y-4">
      <Link
        href={`/vaults/${vaultId}`}
        className="text-sm text-emerald-600 hover:underline"
      >
        Back to vault
      </Link>

      <Card>
        <QueryBoundary state={state}>
          {secret && (
            <>
              <CardHeader
                title={secret.name}
                description={
                  secret.description
                    ? `${secret.description} · v${secret.current_version}`
                    : `Version ${secret.current_version}`
                }
              />

              <div className="space-y-4">
                <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                  <p className="text-sm text-zinc-500">Secret value</p>
                  {revealedValue ? (
                    <p className="mt-2 font-mono text-sm break-all">
                      {revealedValue}
                    </p>
                  ) : (
                    <p className="mt-2 text-sm text-zinc-400">
                      Value hidden. Reveal to view temporarily.
                    </p>
                  )}
                  <div className="mt-3 flex gap-2">
                    <Button
                      variant="secondary"
                      onClick={handleReveal}
                      disabled={reveal.isPending}
                    >
                      {reveal.isPending ? "Revealing…" : "Reveal"}
                    </Button>
                    {revealedValue && (
                      <Button
                        variant="ghost"
                        onClick={() => setRevealedValue(null)}
                      >
                        Hide
                      </Button>
                    )}
                  </div>
                  {reveal.isError && isApiError(reveal.error) && (
                    <p className="mt-2 text-sm text-red-600">
                      {reveal.error.isRateLimited()
                        ? `Rate limited. Retry in ${reveal.error.retryAfter ?? "?"}s.`
                        : "Reveal failed."}
                    </p>
                  )}
                </div>

                {canModify && (
                  <>
                    <form onSubmit={handleRotate} className="space-y-3">
                      <Input
                        label="Rotate to new value"
                        value={newValue}
                        onChange={(e) => setNewValue(e.target.value)}
                        required
                      />
                      <Button type="submit" disabled={rotate.isPending}>
                        Rotate secret
                      </Button>
                    </form>
                    <Button variant="danger" onClick={handleDelete}>
                      Delete secret
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </QueryBoundary>
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
