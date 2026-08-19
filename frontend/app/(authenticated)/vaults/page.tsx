"use client";

import { useState } from "react";
import Link from "next/link";
import { FolderKey, Plus, ChevronRight } from "lucide-react";
import { useAuth } from "@/domains/auth/auth-provider";
import { useVaultsQuery } from "@/domains/vaults/queries";
import { useCreateVaultMutation } from "@/domains/vaults/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StaleIndicator } from "@/components/stale-indicator";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MutationError } from "@/components/mutation-error";

export default function VaultsPage() {
  const { capabilities } = useAuth();
  const vaults = useVaultsQuery();
  const createVault = useCreateVaultMutation();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const state = getQueryState(vaults);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createVault.mutateAsync({
        name,
        description: description || null,
      });
      setName("");
      setDescription("");
      setShowForm(false);
    } catch {
      // shown via MutationError
    }
  };

  return (
    <div>
      <PageHeader
        title="Vaults"
        description="Encrypted containers for your team's secrets."
        action={
          <div className="flex items-center gap-2">
            <StaleIndicator visible={state.isBackgroundFetching} />
            {capabilities?.can_create_vaults && (
              <Button
                variant="secondary"
                onClick={() => setShowForm((v) => !v)}
              >
                <Plus className="h-4 w-4" aria-hidden />
                {showForm ? "Cancel" : "New vault"}
              </Button>
            )}
          </div>
        }
      />

      {showForm && (
        <Card className="mb-6">
          <h2 className="text-sm font-medium text-ink">Create vault</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-3">
            <Input
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={200}
            />
            <Input
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={1000}
            />
            <MutationError error={createVault.error} />
            <Button type="submit" loading={createVault.isPending}>
              Create vault
            </Button>
          </form>
        </Card>
      )}

      <Card>
        <QueryBoundary
          state={state}
          emptyMessage="No vaults yet"
          emptyDescription={
            capabilities?.can_create_vaults
              ? "Create your first vault to start storing secrets securely."
              : "No vaults are available for your role."
          }
          emptyAction={
            capabilities?.can_create_vaults ? (
              <Button variant="secondary" onClick={() => setShowForm(true)}>
                <Plus className="h-4 w-4" aria-hidden />
                Create vault
              </Button>
            ) : undefined
          }
        >
          <ul className="divide-y divide-border">
            {vaults.data?.map((vault) => (
              <li key={vault.id}>
                <Link
                  href={`/vaults/${vault.id}`}
                  className="group flex items-center justify-between gap-4 py-4 transition-colors duration-[var(--transition)] hover:text-primary"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-surface-2 text-muted group-hover:text-primary">
                      <FolderKey className="h-4 w-4" aria-hidden />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-ink group-hover:text-primary">
                        {vault.name}
                      </p>
                      {vault.description && (
                        <p className="mt-0.5 truncate text-sm text-muted">
                          {vault.description}
                        </p>
                      )}
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
    </div>
  );
}
