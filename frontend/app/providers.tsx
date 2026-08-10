"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/domains/auth/auth-provider";
import { getQueryClient } from "@/lib/query/client";

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
