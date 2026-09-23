"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isInitializing, mfaEnrollmentRequired } = useAuth();

  useEffect(() => {
    if (isInitializing) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (mfaEnrollmentRequired) {
      router.replace("/mfa/enroll");
      return;
    }
    router.replace("/vaults");
  }, [isAuthenticated, isInitializing, mfaEnrollmentRequired, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-zinc-500">
      Loading…
    </div>
  );
}
