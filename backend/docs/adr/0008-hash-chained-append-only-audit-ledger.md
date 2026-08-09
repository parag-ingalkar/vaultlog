# ADR 0008: Hash-chained, append-only audit ledger with per-tenant chains

- Status: Accepted
- Date: 2026-08-09

## Context

A secrets manager must provide provable history: who accessed what, when,
and with what outcome. Insider threats include users with database access,
so "the app doesn't provide an update endpoint" is insufficient.

## Decision

- Append-only `audit_event` table; app role holds `SELECT`+`INSERT` only —
  `UPDATE`/`DELETE` are physically impossible at the privilege level.
- Per-tenant hash chains: `entry_hash = SHA-256(previous_hash || canonical)`,
  canonical = sorted-keys, whitespace-free JSON with fixed datetime format.
- Per-tenant chain head row locked with `SELECT ... FOR UPDATE` serializes
  appends and provides the ordering guarantee under concurrency.
- Business mutations and their audit events commit in one tenant-scoped UoW
  transaction. Denials are audited in a separate immediate transaction.
- Audit metadata passes through a forbidden-key guard; plaintext, tokens,
  codes, and keys can never enter the ledger.
- Chain verification (sequence continuity, link integrity, content
  integrity, head consistency) runs in tests and via `scripts/verify_chain.py`.
- Hash chains provide tamper **evidence**, not tamper impossibility: an attacker
  with owner-level DB access can rewrite and recompute. External anchoring
  of chain-head digests is the documented next step.
- Full DDD placement: `domain/audit` owns hashing rules and `AuditService`;
  infrastructure provides `SqlAlchemyAuditRepository`; use cases orchestrate
  after domain mutations.
- RLS policies live in `scripts/rls/policies/` per ADR 0004, not in Alembic.
- Closed `AUDIT_ACTIONS` vocabulary includes future membership/MFA/key events;
  only tenant-scoped vault/secret/grant mutations and `access.denied` emit
  events in this iteration.

## Consequences

- Concurrent writes within one tenant serialize on the chain head (accepted;
  measured by the concurrency integration test).
- Canonicalization is a frozen, versioned format — changing it invalidates
  historical verification and requires a format-version migration.
- Organization deletion is `RESTRICT`ed by audit FKs; org teardown becomes an
  explicit archival procedure, not a cascade.
- Use cases accept `ActorContext` (user, session, tenant) for audit rows.
