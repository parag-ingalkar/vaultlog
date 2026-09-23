"use client";

import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/domains/auth/auth-provider";
import { clearSession } from "@/lib/api/client";
import { onSessionExpired } from "@/lib/auth/session-events";
import { getQueryClient } from "@/lib/query/client";

const PUBLIC_PATHS = new Set(["/login", "/register", "/accept-invite"]);

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  useEffect(() => {
    return onSessionExpired(() => {
      clearSession();
      queryClient.clear();
      const path = window.location.pathname;
      if (PUBLIC_PATHS.has(path)) {
        return;
      }
      window.location.replace("/login");
    });
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
