"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
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
import { BackLink } from "@/components/back-link";
import { CopyButton } from "@/components/copy-button";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
    <div className="space-y-6">
      <BackLink href={`/vaults/${vaultId}`}>Back to vault</BackLink>

      <QueryBoundary state={state}>
        {secret && (
          <>
            <PageHeader
              title={secret.name}
              description={secret.description ?? undefined}
              action={
                <Badge variant="muted">v{secret.current_version}</Badge>
              }
            />

            <Card>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-sm font-medium text-ink">Secret value</h2>
                  <p className="mt-1 text-sm text-muted">
                    Reveal only when you need it. The value clears when you leave
                    this page.
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-[var(--radius-panel)] border border-border bg-surface-2 p-4">
                {revealedValue ? (
                  <p className="font-mono text-sm break-all text-ink">
                    {revealedValue}
                  </p>
                ) : (
                  <p className="font-mono text-sm text-muted">
                    ••••••••••••••••••••
                  </p>
                )}

                <div className="mt-4 flex flex-wrap gap-2">
                  {!revealedValue ? (
                    <Button
                      variant="secondary"
                      onClick={handleReveal}
                      loading={reveal.isPending}
                    >
                      <Eye className="h-4 w-4" aria-hidden />
                      Reveal
                    </Button>
                  ) : (
                    <>
                      <CopyButton value={revealedValue} />
                      <Button
                        variant="ghost"
                        onClick={() => setRevealedValue(null)}
                      >
                        <EyeOff className="h-4 w-4" aria-hidden />
                        Hide
                      </Button>
                    </>
                  )}
                </div>

                {reveal.isError && isApiError(reveal.error) && (
                  <p className="mt-3 text-sm text-danger" role="alert">
                    {reveal.error.isRateLimited()
                      ? `Rate limited. Try again in ${reveal.error.retryAfter ?? "?"}s.`
                      : "Reveal failed."}
                  </p>
                )}
              </div>
            </Card>

            {canModify && (
              <Card>
                <h2 className="text-sm font-medium text-ink">Rotate value</h2>
                <p className="mt-1 text-sm text-muted">
                  Replace the secret with a new value. The previous version is
                  retained in the audit log.
                </p>
                <form onSubmit={handleRotate} className="mt-4 space-y-3">
                  <Input
                    label="New value"
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    required
                  />
                  <Button type="submit" loading={rotate.isPending}>
                    Rotate secret
                  </Button>
                </form>

                <div className="mt-6 border-t border-border pt-4">
                  <Button variant="danger" onClick={handleDelete}>
                    Delete secret
                  </Button>
                </div>
              </Card>
            )}
          </>
        )}
      </QueryBoundary>

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
