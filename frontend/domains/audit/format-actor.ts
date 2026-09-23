import type { AuditActorResponse } from "@/lib/api/types";

export function formatActor(actor: AuditActorResponse | null | undefined): string {
  if (!actor) {
    return "Unknown actor";
  }

  if (!actor.email) {
    return "Unknown actor";
  }

  if (actor.status === "former_member") {
    return `${actor.email} (former member)`;
  }

  if (actor.role) {
    return `${actor.email} (${actor.role})`;
  }

  return actor.email;
}
