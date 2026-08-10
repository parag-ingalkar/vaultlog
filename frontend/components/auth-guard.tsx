"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitializing, mfaEnrollmentRequired } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isInitializing) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (mfaEnrollmentRequired) {
      router.replace("/mfa/enroll");
    }
  }, [isAuthenticated, isInitializing, mfaEnrollmentRequired, router]);

  if (isInitializing || !isAuthenticated || mfaEnrollmentRequired) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-zinc-500">
        Loading session…
      </div>
    );
  }

  return <>{children}</>;
}
