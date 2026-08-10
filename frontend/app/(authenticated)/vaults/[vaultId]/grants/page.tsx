"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useVaultGrantsQuery } from "@/domains/vaults/queries";
import {
  useRevokeGrantMutation,
  useUpsertGrantMutation,
} from "@/domains/vaults/mutations";
import { useMembersQuery } from "@/domains/members/queries";
import { QueryBoundary, getQueryState } from "@/components/query-boundary";
import { BackLink } from "@/components/back-link";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
    <div className="space-y-6">
      <BackLink href={`/vaults/${vaultId}`}>Back to vault</BackLink>

      <PageHeader
        title="Vault grants"
        description="Fine-grained access for specific members. Org roles still apply by default."
      />

      <Card>
        <h2 className="text-sm font-medium text-ink">Add or update grant</h2>
        <form onSubmit={handleUpsert} className="mt-4 space-y-3">
          <Select
            label="Member"
            value={membershipId}
            onChange={(e) => setMembershipId(e.target.value)}
            required
          >
            <option value="" disabled>
              Select a member
            </option>
            {members.data?.map((member) => (
              <option key={member.membership_id} value={member.membership_id}>
                {member.email} ({member.role})
              </option>
            ))}
          </Select>
          <Select
            label="Permission"
            value={permission}
            onChange={(e) =>
              setPermission(e.target.value as VaultPermission)
            }
          >
            <option value="read">Read</option>
            <option value="write">Write</option>
            <option value="admin">Admin</option>
          </Select>
          <Button type="submit" loading={upsertGrant.isPending}>
            Save grant
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-medium text-ink">Active grants</h2>
        <div className="mt-4">
          <QueryBoundary state={grantsState} emptyMessage="No explicit grants">
            <ul className="divide-y divide-border">
              {grants.data?.map((grant) => (
                <li
                  key={grant.membership_id}
                  className="flex flex-wrap items-center justify-between gap-3 py-4"
                >
                  <div>
                    <p className="font-medium text-ink">{grant.email}</p>
                    <p className="mt-0.5 text-sm text-muted">
                      <Badge variant="muted">{grant.permission}</Badge>
                      <span className="ml-2 capitalize">{grant.org_role}</span>
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
        </div>
      </Card>
    </div>
  );
}
