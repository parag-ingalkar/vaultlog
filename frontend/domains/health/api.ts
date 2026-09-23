import { apiRequest } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

export async function checkHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health", { skipAuth: true });
}
