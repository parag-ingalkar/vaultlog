# ADR 0006: Two-axis RBAC (org role + vault grant) via a single policy service

- Status: Accepted
- Date: 2026-08-08

## Context

VaultLog must compartmentalize secrets inside a tenant. A flat org-level role
system would give every member access to every secret; a purely grant-based
system would make org administration awkward and leave orphaned grants when
roles change.

## Decision

- Organization roles (owner/admin/member/viewer) provide baseline capabilities;
  vault grants (read/write/admin) gate vault contents.
- Owner/admin synthesize vault-admin permission without grant rows.
- Viewers are hard-capped at read regardless of grant data (policy > data).
- All decisions flow through `PolicyService` in the domain layer; routers and
  use cases never implement ad-hoc role checks.
- Authorization failures split into 404 (invisible/nonexistent) and 403
  (visible, denied) to prevent IDOR existence leaks.
- Step-up proof is re-asserted inside destructive use cases, not only in router
  dependencies.

## Consequences

- The permission matrix is executable specification: tests are generated from it
  and must be updated with any behavior change.
- Listing endpoints need the `None`-vs-list contract for unrestricted roles.
- ABAC attributes (IP, time, classification) can later extend `AccessContext`
  without changing call sites.

Note: VaultLogBook labels this ADR as 0005; in this repository ADR 0005 is
reserved for TOTP MFA and step-up authentication.
