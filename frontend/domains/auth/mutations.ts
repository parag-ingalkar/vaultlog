import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  storeAccessTokenFromResponse,
  clearSession,
} from "@/lib/api/client";
import { withStepUp } from "@/lib/auth/with-step-up";
import { setStepUpToken } from "@/lib/auth/step-up-cache";
import { clearAllStepUpTokens } from "@/lib/auth/step-up-cache";
import { invalidateSession } from "@/lib/query/invalidation";
import { queryKeys } from "@/lib/query/keys";
import type {
  LoginRequest,
  MfaVerifyRequest,
  RegisterRequest,
  StepUpRequest,
} from "@/lib/api/types";
import {
  confirmMfa,
  disableMfa,
  enrollMfa,
  isMfaRequiredResponse,
  login,
  logout,
  register,
  verifyMfa,
  verifyStepUp,
} from "./api";

export function useRegisterMutation() {
  return useMutation({
    mutationFn: (body: RegisterRequest) => register(body),
  });
}

export function useLoginMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: LoginRequest) => {
      const response = await login(body);
      if (!isMfaRequiredResponse(response)) {
        storeAccessTokenFromResponse(response);
      }
      // #region agent log
      fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'mutations.ts:login',message:'login mutationFn complete',data:{mfaRequired:isMfaRequiredResponse(response),hasToken:!isMfaRequiredResponse(response)},timestamp:Date.now(),hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      return response;
    },
    onSuccess: async (data) => {
      if (!isMfaRequiredResponse(data)) {
        await invalidateSession(queryClient);
        // #region agent log
        fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'mutations.ts:login:onSuccess',message:'invalidateSession complete',data:{meQueryState:queryClient.getQueryState(queryKeys.auth.me())?.status,meData:!!queryClient.getQueryData(queryKeys.auth.me())},timestamp:Date.now(),hypothesisId:'B'})}).catch(()=>{});
        // #endregion
      }
    },
  });
}

export function useVerifyMfaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: MfaVerifyRequest) => verifyMfa(body),
    onSuccess: async () => {
      await invalidateSession(queryClient);
    },
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearSession();
      clearAllStepUpTokens();
      queryClient.clear();
    },
  });
}

export function useEnrollMfaMutation() {
  return useMutation({
    mutationFn: enrollMfa,
  });
}

export function useConfirmMfaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (code: string) => confirmMfa(code),
    onSuccess: async () => {
      await invalidateSession(queryClient);
    },
  });
}

export function useStepUpMutation() {
  return useMutation({
    mutationFn: (body: StepUpRequest) => verifyStepUp(body),
    onSuccess: (data, variables) => {
      setStepUpToken(variables.purpose, data.step_up_token, data.expires_in);
    },
  });
}

export function useDisableMfaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      withStepUp("step-up:manage-mfa", (token) => disableMfa(token)),
    onSuccess: async () => {
      await invalidateSession(queryClient);
    },
  });
}
