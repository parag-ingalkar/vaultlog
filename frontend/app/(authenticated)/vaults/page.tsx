"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/domains/auth/auth-provider";
import { useVaultsQuery } from "@/domains/vaults/queries";
import { useCreateVaultMutation } from "@/domains/vaults/mutations";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { StaleIndicator } from "@/components/stale-indicator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";

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
    await createVault.mutateAsync({
      name,
      description: description || null,
    });
    setName("");
    setDescription("");
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
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
                  {showForm ? "Cancel" : "New vault"}
                </Button>
              )}
            </div>
          }
        />

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="mb-6 space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
          >
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
            <Button type="submit" disabled={createVault.isPending}>
              Create vault
            </Button>
          </form>
        )}

        <QueryBoundary
          state={state}
          emptyMessage={
            capabilities?.can_create_vaults
              ? "No vaults yet. Create your first vault."
              : "No vaults available."
          }
        >
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {vaults.data?.map((vault) => (
              <li key={vault.id} className="py-3">
                <Link
                  href={`/vaults/${vault.id}`}
                  className="block hover:text-emerald-600"
                >
                  <p className="font-medium">{vault.name}</p>
                  {vault.description && (
                    <p className="text-sm text-zinc-500">{vault.description}</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </QueryBoundary>
      </Card>
    </div>
  );
}
