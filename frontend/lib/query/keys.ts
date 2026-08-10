import type { AuditFilters } from "@/lib/api/types";

export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    me: () => [...queryKeys.auth.all, "me"] as const,
  },
  organization: {
    all: ["organization"] as const,
    detail: () => [...queryKeys.organization.all, "detail"] as const,
  },
  vaults: {
    all: ["vaults"] as const,
    lists: () => [...queryKeys.vaults.all, "list"] as const,
    list: () => [...queryKeys.vaults.lists()] as const,
    details: () => [...queryKeys.vaults.all, "detail"] as const,
    detail: (vaultId: string) =>
      [...queryKeys.vaults.details(), vaultId] as const,
    grants: (vaultId: string) =>
      [...queryKeys.vaults.detail(vaultId), "grants"] as const,
  },
  secrets: {
    all: ["secrets"] as const,
    lists: () => [...queryKeys.secrets.all, "list"] as const,
    list: (vaultId: string) => [...queryKeys.secrets.lists(), vaultId] as const,
  },
  members: {
    all: ["members"] as const,
    list: () => [...queryKeys.members.all, "list"] as const,
  },
  invitations: {
    all: ["invitations"] as const,
    list: () => [...queryKeys.invitations.all, "list"] as const,
    preview: (token: string) =>
      [...queryKeys.invitations.all, "preview", token] as const,
  },
  audit: {
    all: ["audit"] as const,
    lists: () => [...queryKeys.audit.all, "list"] as const,
    list: (filters: AuditFilters) =>
      [...queryKeys.audit.lists(), filters] as const,
  },
};
