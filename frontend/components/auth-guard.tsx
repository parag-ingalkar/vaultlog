"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";
import { ListSkeleton } from "@/components/ui/skeleton";

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
      <div className="flex min-h-screen items-center justify-center bg-bg px-4">
        <div className="w-full max-w-md">
          <ListSkeleton rows={2} />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
