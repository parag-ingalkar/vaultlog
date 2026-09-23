import type { components } from "./schema";

export type Schemas = components["schemas"];

export type MeResponse = Schemas["MeResponse"];
export type AccessTokenResponse = Schemas["AccessTokenResponse"];
export type MfaRequiredResponse = Schemas["MfaRequiredResponse"];
export type RegisterRequest = Schemas["RegisterRequest"];
export type RegisterResponse = Schemas["RegisterResponse"];
export type LoginRequest = Schemas["LoginRequest"];
export type MfaVerifyRequest = Schemas["MfaVerifyRequest"];
export type EnrollmentResponse = Schemas["EnrollmentResponse"];
export type RecoveryCodesResponse = Schemas["RecoveryCodesResponse"];
export type StepUpRequest = Schemas["StepUpRequest"];
export type StepUpResponse = Schemas["StepUpResponse"];
export type StepUpPurpose = Schemas["StepUpPurpose"];
export type UserCapabilities = Schemas["UserCapabilitiesResponse"];
export type OrgRole = Schemas["OrgRole"];
export type VaultPermission = Schemas["VaultPermission"];

export type OrganizationResponse = Schemas["OrganizationResponse"];
export type VaultResponse = Schemas["VaultResponse"];
export type VaultCreateRequest = Schemas["VaultCreateRequest"];
export type VaultUpdateRequest = Schemas["VaultUpdateRequest"];
export type GrantRequest = Schemas["GrantRequest"];
export type GrantResponse = Schemas["GrantResponse"];

export type SecretMetaResponse = Schemas["SecretMetaResponse"];
export type SecretCreateRequest = Schemas["SecretCreateRequest"];
export type RevealResponse = Schemas["RevealResponse"];
export type RotateSecretRequest = Schemas["RotateSecretRequest"];

export type MemberResponse = Schemas["MemberResponse"];
export type InvitationResponse = Schemas["InvitationResponse"];
export type InvitationCreateRequest = Schemas["InvitationCreateRequest"];
export type InvitationPreviewResponse = Schemas["InvitationPreviewResponse"];
export type AcceptInvitationRequest = Schemas["AcceptInvitationRequest"];

export type AuditEventResponse = Schemas["AuditEventResponse"];
export type AuditActorResponse = Schemas["AuditActorResponse"];
export type HealthResponse = Schemas["HealthResponse"];

export type AuditFilters = {
  action?: string;
  target_id?: string;
  before_sequence?: number;
  limit?: number;
};
