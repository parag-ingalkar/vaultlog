"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { KeyRound, Plus, Users, ChevronRight } from "lucide-react";
import { useVaultQuery } from "@/domains/vaults/queries";
import {
  useDeleteVaultMutation,
  useUpdateVaultMutation,
} from "@/domains/vaults/mutations";
import { useSecretsQuery } from "@/domains/secrets/queries";
import { useCreateSecretMutation } from "@/domains/secrets/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StaleIndicator } from "@/components/stale-indicator";
import { StepUpModal } from "@/components/step-up-modal";
import { useStepUpHandler } from "@/hooks/use-step-up-handler";
import { usePermissions } from "@/hooks/use-permissions";
import { BackLink } from "@/components/back-link";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MutationError } from "@/components/mutation-error";

export default function VaultDetailPage() {
  const params = useParams<{ vaultId: string }>();
  const vaultId = params.vaultId;
  const router = useRouter();
  const { canWriteSecrets, canManageGrants } = usePermissions();
  const vault = useVaultQuery(vaultId);
  const secrets = useSecretsQuery(vaultId);
  const updateVault = useUpdateVaultMutation(vaultId);
  const deleteVault = useDeleteVaultMutation();
  const createSecret = useCreateSecretMutation(vaultId);
  const { stepUpState, clearStepUp, handleStepUpError } = useStepUpHandler();

  const [editName, setEditName] = useState("");
  const [showSecretForm, setShowSecretForm] = useState(false);
  const [secretName, setSecretName] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [secretDescription, setSecretDescription] = useState("");

  const vaultState = getQueryState(vault);
  const secretsState = getQueryState(secrets);

  const canManage = canManageGrants;
  const canCreateSecret = canWriteSecrets;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName) return;
    try {
      await updateVault.mutateAsync({ name: editName });
      setEditName("");
    } catch {
      // shown via MutationError
    }
  };

  const handleDelete = async () => {
    try {
      await deleteVault.mutateAsync(vaultId);
      router.push("/vaults");
    } catch (error) {
      handleStepUpError(error, "step-up:delete-vault", () =>
        deleteVault.mutateAsync(vaultId),
      );
    }
  };

  const handleCreateSecret = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createSecret.mutateAsync({
        name: secretName,
        value: secretValue,
        description: secretDescription || null,
      });
      setSecretName("");
      setSecretValue("");
      setSecretDescription("");
      setShowSecretForm(false);
    } catch {
      // shown via MutationError
    }
  };

  return (
    <div className="space-y-6">
      <BackLink href="/vaults">All vaults</BackLink>

      <QueryBoundary state={vaultState} loadingRows={2}>
        {vault.data && (
          <PageHeader
            title={vault.data.name}
            description={vault.data.description ?? undefined}
            action={
              <div className="flex items-center gap-2">
                <StaleIndicator visible={vaultState.isBackgroundFetching} />
                {canManage && (
                  <Link href={`/vaults/${vaultId}/grants`}>
                    <Button variant="secondary">
                      <Users className="h-4 w-4" aria-hidden />
                      Grants
                    </Button>
                  </Link>
                )}
              </div>
            }
          />
        )}
      </QueryBoundary>

      {canManage && vault.data && (
        <Card>
          <h2 className="text-sm font-medium text-ink">Vault settings</h2>
          <form onSubmit={handleUpdate} className="mt-4 space-y-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <Input
                  label="Rename vault"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder={vault.data.name}
                />
              </div>
              <Button type="submit" variant="secondary" disabled={!editName}>
                Save name
              </Button>
            </div>
            <MutationError error={updateVault.error} />
          </form>
          <div className="mt-4 border-t border-border pt-4">
            <Button variant="danger" onClick={handleDelete}>
              Delete vault
            </Button>
          </div>
        </Card>
      )}

      <Card>
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">Secrets</h2>
            <p className="mt-1 text-sm text-muted">
              Metadata only — values are revealed on the detail page.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StaleIndicator visible={secretsState.isBackgroundFetching} />
            {canCreateSecret && (
              <Button
                variant="secondary"
                onClick={() => setShowSecretForm((v) => !v)}
              >
                <Plus className="h-4 w-4" aria-hidden />
                {showSecretForm ? "Cancel" : "New secret"}
              </Button>
            )}
          </div>
        </div>

        {showSecretForm && (
          <form
            onSubmit={handleCreateSecret}
            className="mb-6 space-y-3 rounded-[var(--radius-panel)] border border-border bg-surface-2 p-4"
          >
            <Input
              label="Name"
              value={secretName}
              onChange={(e) => setSecretName(e.target.value)}
              required
            />
            <Input
              label="Value"
              value={secretValue}
              onChange={(e) => setSecretValue(e.target.value)}
              required
            />
            <Input
              label="Description"
              value={secretDescription}
              onChange={(e) => setSecretDescription(e.target.value)}
            />
            <MutationError error={createSecret.error} />
            <Button type="submit" loading={createSecret.isPending}>
              Create secret
            </Button>
          </form>
        )}

        <QueryBoundary
          state={secretsState}
          emptyMessage="No secrets yet"
          emptyDescription="Add a secret to store credentials, API keys, or tokens."
          emptyAction={
            canCreateSecret ? (
              <Button variant="secondary" onClick={() => setShowSecretForm(true)}>
                <Plus className="h-4 w-4" aria-hidden />
                Add secret
              </Button>
            ) : undefined
          }
        >
          <ul className="divide-y divide-border">
            {secrets.data?.map((secret) => (
              <li key={secret.id}>
                <Link
                  href={`/vaults/${vaultId}/secrets/${secret.id}`}
                  className="group flex items-center justify-between gap-4 py-4"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-surface-2 text-muted group-hover:text-primary">
                      <KeyRound className="h-4 w-4" aria-hidden />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-ink group-hover:text-primary">
                        {secret.name}
                      </p>
                      <p className="mt-0.5 text-sm text-muted">
                        v{secret.current_version}
                        {secret.description ? ` · ${secret.description}` : ""}
                      </p>
                    </div>
                  </div>
                  <ChevronRight
                    className="h-4 w-4 shrink-0 text-muted group-hover:text-primary"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
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
