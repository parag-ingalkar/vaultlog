import { apiRequest, refreshSession, clearSession } from "@/lib/api/client";
import { hasAccessToken } from "@/lib/auth/token-store";
import type { MeResponse } from "@/lib/api/types";

export async function bootstrapSession(): Promise<MeResponse | null> {
  try {
    if (!hasAccessToken()) {
      await refreshSession();
    }
    return await apiRequest<MeResponse>("/auth/me");
  } catch {
    clearSession();
    return null;
  }
}
