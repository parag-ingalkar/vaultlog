"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useVaultGrantsQuery } from "@/domains/vaults/queries";
import {
  useRevokeGrantMutation,
  useUpsertGrantMutation,
} from "@/domains/vaults/mutations";
import { useMembersQuery } from "@/domains/members/queries";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader } from "@/components/ui/card";
import type { VaultPermission } from "@/lib/api/types";

export default function VaultGrantsPage() {
  const params = useParams<{ vaultId: string }>();
  const vaultId = params.vaultId;
  const grants = useVaultGrantsQuery(vaultId);
  const members = useMembersQuery();
  const upsertGrant = useUpsertGrantMutation(vaultId);
  const revokeGrant = useRevokeGrantMutation(vaultId);

  const [membershipId, setMembershipId] = useState("");
  const [permission, setPermission] = useState<VaultPermission>("read");

  const grantsState = getQueryState(grants);

  const handleUpsert = async (e: React.FormEvent) => {
    e.preventDefault();
    await upsertGrant.mutateAsync({ membership_id: membershipId, permission });
    setMembershipId("");
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
        <CardHeader
          title="Vault grants"
          description="Explicit per-member permissions for this vault."
        />

        <form onSubmit={handleUpsert} className="mb-6 space-y-3">
          <Input
            label="Membership ID"
            value={membershipId}
            onChange={(e) => setMembershipId(e.target.value)}
            required
            placeholder="UUID from team members list"
          />
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Permission
            <select
              className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={permission}
              onChange={(e) =>
                setPermission(e.target.value as VaultPermission)
              }
            >
              <option value="read">read</option>
              <option value="write">write</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <Button type="submit" disabled={upsertGrant.isPending}>
            Upsert grant
          </Button>
        </form>

        <QueryBoundary state={grantsState} emptyMessage="No explicit grants.">
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {grants.data?.map((grant) => (
              <li
                key={grant.membership_id}
                className="flex items-center justify-between py-3"
              >
                <div>
                  <p className="font-medium">{grant.email}</p>
                  <p className="text-sm text-zinc-500">
                    {grant.permission} · {grant.org_role}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => revokeGrant.mutate(grant.membership_id)}
                >
                  Revoke
                </Button>
              </li>
            ))}
          </ul>
        </QueryBoundary>
      </Card>

      <Card>
        <CardHeader
          title="Members reference"
          description="Use membership_id when creating grants."
        />
        <ul className="divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
          {members.data?.map((member) => (
            <li key={member.membership_id} className="py-2">
              <span className="font-medium">{member.email}</span>
              <span className="text-zinc-500"> · {member.membership_id}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
