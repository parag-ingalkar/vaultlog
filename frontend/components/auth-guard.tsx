"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitializing, mfaEnrollmentRequired } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isInitializing) return;
    // #region agent log
    fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'auth-guard.tsx:redirect',message:'auth guard check',data:{isAuthenticated,isInitializing,mfaEnrollmentRequired,redirectTo:!isAuthenticated?'/login':mfaEnrollmentRequired?'/mfa/enroll':null},timestamp:Date.now(),hypothesisId:'C'})}).catch(()=>{});
    // #endregion
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
