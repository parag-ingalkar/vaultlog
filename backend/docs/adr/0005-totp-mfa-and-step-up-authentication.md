# ADR 0005: TOTP MFA with challenge tokens, plus purpose-scoped step-up tokens

- Status: Accepted
- Date: 2026-08-08

## Context

Secrets management demands that password compromise alone cannot grant access,
and that sensitive actions in an existing session require fresh proof of
identity. Session hijacking must not enable destructive operations.

## Decision

- TOTP (RFC 6238) as the second factor; seeds encrypted at rest with
  AES-256-GCM under a dedicated KEK, AAD-bound to the user ID.
- Two-phase enrollment: MFA activates only after a valid code is presented.
- MFA-enabled logins receive a 5-minute single-purpose challenge token
  (`purpose=mfa-challenge`); no session or refresh token exists until MFA passes.
- Recovery codes: 10 single-use codes, SHA-256 hashed at rest, shown once.
- Step-up: 5-minute JWT bound to user, session, and a specific purpose;
  required for deleting vaults/secrets, removing members, key rotation,
  and MFA management. Delivered via `X-Step-Up-Token` header.
- WebAuthn/passkeys deferred; the challenge/step-up architecture is designed
  to accommodate them later (challenge token gains a webauthn branch).

## Consequences

- Clients must handle the two-step login and the 403 → step-up retry flow.
- TOTP seed loss without recovery codes means account recovery is a
  manual, organization-owner-mediated process (documented runbook needed).
- Clock drift tolerated to one 30-second window; rate limiting (Chapter 8)
  is load-bearing for brute-force resistance.
