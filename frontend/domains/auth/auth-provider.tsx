"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { bootstrapSession } from "@/lib/auth/session-bootstrap";
import { hasAccessToken } from "@/lib/auth/token-store";
import { queryKeys } from "@/lib/query/keys";
import type { MeResponse } from "@/lib/api/types";
import { useMeQuery } from "./queries";

type AuthContextValue = {
  me: MeResponse | undefined;
  isAuthenticated: boolean;
  isInitializing: boolean;
  isLoading: boolean;
  mfaEnrollmentRequired: boolean;
  capabilities: MeResponse["capabilities"] | undefined;
  refetchMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [bootstrapped, setBootstrapped] = useState(false);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const me = await bootstrapSession();
        if (!cancelled && me) {
          queryClient.setQueryData(queryKeys.auth.me(), me);
        }
      } finally {
        if (!cancelled) {
          setBootstrapped(true);
          setInitializing(false);
        }
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [queryClient]);

  const meQueryEnabled = bootstrapped && hasAccessToken();
  const meQuery = useMeQuery(meQueryEnabled);

  // #region agent log
  useEffect(() => {
    fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'auth-provider.tsx:meQuery',message:'auth state snapshot',data:{bootstrapped,meQueryEnabled,hasToken:hasAccessToken(),meStatus:meQuery.status,hasMeData:!!meQuery.data,mfaEnrollmentRequired:meQuery.data?.mfa_enrollment_required},timestamp:Date.now(),hypothesisId:'B'})}).catch(()=>{});
  }, [bootstrapped, meQueryEnabled, meQuery.status, meQuery.data]);
  // #endregion

  const refetchMe = useCallback(async () => {
    await meQuery.refetch();
  }, [meQuery]);

  const value = useMemo<AuthContextValue>(
    () => ({
      me: meQuery.data,
      isAuthenticated: Boolean(meQuery.data),
      isInitializing: initializing || (bootstrapped && meQuery.isLoading),
      isLoading: meQuery.isLoading,
      mfaEnrollmentRequired:
        meQuery.data?.mfa_enrollment_required ?? false,
      capabilities: meQuery.data?.capabilities,
      refetchMe,
    }),
    [meQuery.data, meQuery.isLoading, initializing, bootstrapped, refetchMe],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
