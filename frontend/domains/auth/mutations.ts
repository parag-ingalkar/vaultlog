import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  storeAccessTokenFromResponse,
  clearSession,
} from "@/lib/api/client";
import { withStepUp } from "@/lib/auth/with-step-up";
import { setStepUpToken } from "@/lib/auth/step-up-cache";
import { clearAllStepUpTokens } from "@/lib/auth/step-up-cache";
import { invalidateSession } from "@/lib/query/invalidation";
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
      return response;
    },
    onSuccess: async (data) => {
      if (!isMfaRequiredResponse(data)) {
        await invalidateSession(queryClient);
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
