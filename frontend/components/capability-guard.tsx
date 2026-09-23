"use client";

import { EmptyState } from "@/components/ui/empty-state";

export function CapabilityGuard({
  allowed,
  title = "Access denied",
  description = "You do not have permission to view this page.",
  children,
}: {
  allowed: boolean;
  title?: string;
  description?: string;
  children: React.ReactNode;
}) {
  if (!allowed) {
    return <EmptyState title={title} description={description} />;
  }

  return <>{children}</>;
}
