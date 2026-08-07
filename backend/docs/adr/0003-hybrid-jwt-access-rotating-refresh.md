# ADR 0003: Short-lived JWT access tokens with rotating, server-tracked refresh tokens

- Status: Accepted
- Date: 2026-07-29

## Context

VaultLog manages secrets, so stolen credentials are a top-tier threat.
Pure stateless JWTs cannot be revoked; pure server sessions sacrifice
stateless verification for ordinary requests.

## Decision

- RS256 JWT access tokens, 10-minute TTL, verified without DB lookups.
- Opaque refresh tokens (384-bit random), SHA-256 hashed at rest,
  rotated on every use, delivered via HttpOnly Secure SameSite=Lax cookies
  scoped to /api/v1/auth.
- Refresh reuse revokes the entire session family.
- Identity/session tables are global (no RLS); access runs through a
  dedicated owner-role `IdentityUnitOfWork` used ONLY for pre-tenant
  operations (register, login, refresh, logout). The owner role has
  `BYPASSRLS` so FORCE RLS on tenant tables does not block org creation
  or membership lookup before a tenant is selected.
- Domain auth rules live in `IdentityService`; application use cases only
  open the UoW, call the service, and commit. Domain exceptions bubble to
  presentation exception handlers that map them to HTTP status codes.
- Persistence and crypto collaborators are `typing.Protocol` ports so
  domain logic can be unit-tested with in-memory fakes.

## Consequences

- Access tokens remain valid up to 10 minutes after revocation (accepted risk;
  sensitive operations will require step-up auth anyway).
- Token theft is detectable via reuse and recoverable via family revocation.
- The owner-role identity path must be reviewed as security-critical code.
- Refresh use cases must commit before re-raising auth errors so reuse and
  expiry revocations persist even when the client receives 401.
