import type { AuditEventResponse } from "@/lib/api/types";

function truncateId(id: string | null | undefined): string | null {
  if (!id) {
    return null;
  }
  if (id.length <= 12) {
    return id;
  }
  return `…${id.slice(-8)}`;
}

function metadataString(
  metadata: AuditEventResponse["metadata"],
  key: string,
): string | null {
  const value = metadata[key];
  if (value === undefined || value === null) {
    return null;
  }
  return String(value);
}

export function formatEventSummary(event: AuditEventResponse): string | null {
  const { action, metadata, target_type, target_id } = event;
  const shortTargetId = truncateId(target_id);

  switch (action) {
    case "vault.created": {
      const name = metadataString(metadata, "name");
      return name ? `Vault "${name}"` : "Vault created";
    }
    case "vault.updated":
      return shortTargetId ? `Vault ${shortTargetId}` : "Vault updated";
    case "vault.deleted":
      return shortTargetId ? `Vault ${shortTargetId}` : "Vault deleted";
    case "grant.created":
    case "grant.updated": {
      const permission = metadataString(metadata, "permission");
      const membershipId = truncateId(metadataString(metadata, "membership_id"));
      const parts = ["Grant"];
      if (permission) {
        parts.push(permission);
      }
      if (membershipId) {
        parts.push(`for member ${membershipId}`);
      }
      return parts.join(" ");
    }
    case "grant.revoked": {
      const membershipId = truncateId(metadataString(metadata, "membership_id"));
      return membershipId
        ? `Revoked grant for member ${membershipId}`
        : "Grant revoked";
    }
    case "secret.created":
    case "secret.revealed":
    case "secret.rotated":
    case "secret.deleted": {
      const vaultId = truncateId(metadataString(metadata, "vault_id"));
      const version =
        metadataString(metadata, "version") ??
        metadataString(metadata, "new_version");
      const parts = [`${target_type} ${shortTargetId ?? ""}`.trim()];
      if (vaultId) {
        parts.push(`in vault ${vaultId}`);
      }
      if (version) {
        parts.push(`version ${version}`);
      }
      return parts.join(" · ");
    }
    case "member.invited": {
      const email = metadataString(metadata, "email");
      const role = metadataString(metadata, "role");
      if (email && role) {
        return `Invited ${email} as ${role}`;
      }
      if (email) {
        return `Invited ${email}`;
      }
      return "Member invited";
    }
    case "member.removed": {
      const userId = truncateId(metadataString(metadata, "user_id"));
      const role = metadataString(metadata, "role");
      if (userId && role) {
        return `Removed member ${userId} (${role})`;
      }
      if (userId) {
        return `Removed member ${userId}`;
      }
      return "Member removed";
    }
    case "member.role_changed": {
      const role = metadataString(metadata, "role");
      return role ? `Role changed to ${role}` : "Member role changed";
    }
    case "access.denied": {
      const attempted = metadataString(metadata, "attempted_action");
      const parts = ["Access denied"];
      if (attempted) {
        parts.push(`for ${attempted}`);
      }
      if (shortTargetId) {
        parts.push(`on ${target_type} ${shortTargetId}`);
      }
      return parts.join(" ");
    }
    case "mfa.enabled":
      return "MFA enabled";
    case "mfa.disabled":
      return "MFA disabled";
    case "key.rotated":
      return "Encryption key rotated";
    case "stepup.issued":
      return "Step-up authentication issued";
    default:
      if (shortTargetId) {
        return `${target_type} ${shortTargetId}`;
      }
      return null;
  }
}

export function formatActionLabel(action: string): string {
  return action.replaceAll(".", " ");
}
