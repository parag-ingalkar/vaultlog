# ADR 0007: Envelope encryption — per-tenant versioned DEKs wrapped by a KMS KEK

- Status: Accepted
- Date: 2026-08-09

## Context

Secrets must survive database dumps, backup leaks, and insider DB access.
Keys must be rotatable without re-encrypting all data or causing downtime.
Compromise of one tenant must not affect others.

## Decision

- AES-256-GCM (AEAD) for all encryption; random 96-bit nonces, never reused.
- Per-tenant, versioned DEKs encrypt secret values; DEKs are stored only
  wrapped by a KEK via a `KEKProvider` interface (local env-var KEK in dev,
  Cloud KMS in production).
- AAD binds every ciphertext to tenant/vault/secret/version and every
  wrapped DEK to tenant/version; AAD is derived, never stored.
- Secret versions are immutable and DB-enforced (app role lacks UPDATE/DELETE
  on `secret_version`); value rotation appends versions.
- Plaintext appears only in reveal responses (POST, `Cache-Control: no-store`)
  and never in logs, audit rows, list endpoints, or error messages.
- Tenant DEK v1 is provisioned in a tenant-scoped UoW immediately after
  registration commits (idempotent, one retry).

## MVP scope (explicit exclusions)

- DEK rotation (`rotate_tenant_dek`) and batch re-encryption sweeps are deferred.
- KEK rotation (re-wrap only) is deferred.
- Audit ledger hooks for secret operations are deferred to Chapter 7.

## Consequences

- Application compromise is out of scope for at-rest encryption (documented);
  mitigated by auth, RLS, RBAC, step-up, and audit layers.
- Key versions must be retained until a verified sweep shows zero references
  when rotation is implemented.
- Python cannot guarantee memory scrubbing of DEKs; lifetime is minimized
  instead. Documented as accepted residual risk.
- Registration uses two transactions (identity then tenant key provision);
  provision failure after identity commit surfaces as HTTP 500 with retry
  semantics in the use case.
