"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";

export default function VaultDetailPage() {
  const params = useParams<{ vaultId: string }>();
  const vaultId = params.vaultId;
  const router = useRouter();
  const { capabilities, me } = useAuth();
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

  const canManage =
    capabilities?.can_create_vaults ?? false;
  const canCreateSecret = me?.role !== "viewer";

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName) return;
    await updateVault.mutateAsync({ name: editName });
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
    await createSecret.mutateAsync({
      name: secretName,
      value: secretValue,
      description: secretDescription || null,
    });
    setSecretName("");
    setSecretValue("");
    setSecretDescription("");
    setShowSecretForm(false);
  };

  return (
    <div className="space-y-4">
      <Card>
        <QueryBoundary state={vaultState}>
          {vault.data && (
            <>
              <CardHeader
                title={vault.data.name}
                description={vault.data.description ?? undefined}
                action={
                  <div className="flex items-center gap-2">
                    <StaleIndicator visible={vaultState.isBackgroundFetching} />
                    <Link
                      href={`/vaults/${vaultId}/grants`}
                      className="text-sm text-emerald-600 hover:underline"
                    >
                      Grants
                    </Link>
                  </div>
                }
              />
              {canManage && (
                <div className="space-y-4">
                  <form onSubmit={handleUpdate} className="flex gap-2">
                    <Input
                      label="Rename vault"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder={vault.data.name}
                    />
                    <Button type="submit" variant="secondary" className="mt-6">
                      Save
                    </Button>
                  </form>
                  <Button variant="danger" onClick={handleDelete}>
                    Delete vault
                  </Button>
                </div>
              )}
            </>
          )}
        </QueryBoundary>
      </Card>

      <Card>
        <CardHeader
          title="Secrets"
          description="Metadata only — values are never shown in the list."
          action={
            <div className="flex items-center gap-2">
              <StaleIndicator visible={secretsState.isBackgroundFetching} />
              {canCreateSecret && (
                <Button
                  variant="secondary"
                  onClick={() => setShowSecretForm((v) => !v)}
                >
                  {showSecretForm ? "Cancel" : "New secret"}
                </Button>
              )}
            </div>
          }
        />

        {showSecretForm && (
          <form
            onSubmit={handleCreateSecret}
            className="mb-4 space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
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
            <Button type="submit" disabled={createSecret.isPending}>
              Create secret
            </Button>
          </form>
        )}

        <QueryBoundary
          state={secretsState}
          emptyMessage="No secrets in this vault yet."
        >
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {secrets.data?.map((secret) => (
              <li key={secret.id} className="py-3">
                <Link
                  href={`/vaults/${vaultId}/secrets/${secret.id}`}
                  className="block hover:text-emerald-600"
                >
                  <p className="font-medium">{secret.name}</p>
                  <p className="text-sm text-zinc-500">
                    v{secret.current_version}
                    {secret.description ? ` · ${secret.description}` : ""}
                  </p>
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
