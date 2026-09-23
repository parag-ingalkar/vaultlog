import { apiRequest } from "@/lib/api/client";
import type { OrganizationResponse } from "@/lib/api/types";

export async function getOrganization(): Promise<OrganizationResponse> {
  return apiRequest<OrganizationResponse>("/organization");
}
