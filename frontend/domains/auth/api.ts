import {
  apiRequest,
  storeAccessTokenFromResponse,
  clearSession,
} from "@/lib/api/client";
import type {
  AccessTokenResponse,
  EnrollmentResponse,
  LoginRequest,
  MeResponse,
  MfaRequiredResponse,
  MfaVerifyRequest,
  RecoveryCodesResponse,
  RegisterRequest,
  RegisterResponse,
  StepUpRequest,
  StepUpResponse,
} from "@/lib/api/types";

export async function register(
  body: RegisterRequest,
): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>("/auth/register", {
    method: "POST",
    body,
    skipAuth: true,
  });
}

export async function login(
  body: LoginRequest,
): Promise<AccessTokenResponse | MfaRequiredResponse> {
  return apiRequest<AccessTokenResponse | MfaRequiredResponse>("/auth/login", {
    method: "POST",
    body,
    skipAuth: true,
  });
}

export async function verifyMfa(
  body: MfaVerifyRequest,
): Promise<AccessTokenResponse> {
  const data = await apiRequest<AccessTokenResponse>("/auth/mfa/verify", {
    method: "POST",
    body,
    skipAuth: true,
  });
  storeAccessTokenFromResponse(data);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>("/auth/logout", { method: "POST", skipAuth: true });
  } finally {
    clearSession();
  }
}

export async function getMe(): Promise<MeResponse> {
  return apiRequest<MeResponse>("/auth/me");
}

export async function enrollMfa(): Promise<EnrollmentResponse> {
  return apiRequest<EnrollmentResponse>("/auth/mfa/enroll", { method: "POST" });
}

export async function confirmMfa(code: string): Promise<RecoveryCodesResponse> {
  return apiRequest<RecoveryCodesResponse>("/auth/mfa/confirm", {
    method: "POST",
    body: { code },
  });
}

export async function verifyStepUp(
  body: StepUpRequest,
): Promise<StepUpResponse> {
  return apiRequest<StepUpResponse>("/auth/step-up/verify", {
    method: "POST",
    body,
  });
}

export async function disableMfa(stepUpToken: string): Promise<void> {
  return apiRequest<void>("/auth/mfa", {
    method: "DELETE",
    stepUpToken,
  });
}

export function isMfaRequiredResponse(
  response: AccessTokenResponse | MfaRequiredResponse,
): response is MfaRequiredResponse {
  return "challenge_token" in response && "mfa_required" in response;
}
