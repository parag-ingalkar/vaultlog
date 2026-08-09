# ADR 0009: Hardening controls and CI enforcement

- Status: Accepted
- Date: 2026-08-09

## Context

Cryptographic strength assumes online throttling; error paths leak more than success
paths; cookie flows carry CSRF exposure; dependencies and committed secrets are top
breach vectors. Design security without operational enforcement decays silently.

## Decision

- Sliding-window rate limiting backed by Redis in **all** environments (Compose
  locally, managed Redis in production). In-memory buckets exist only for isolated
  unit tests of limiter math. Redis holds disposable counters only — sessions and
  durable state stay in PostgreSQL.
- Fail-closed on credential endpoints (login, register, MFA verify, step-up, MFA
  enroll); fail-open on availability endpoints (refresh, reveal) when Redis is down.
- Account-keyed login limits enforced in the domain via `RateLimitGate`; IP/user
  limits enforced in presentation `Depends` and return HTTP 429.
- Unified error contract: `{"error": {"code", "message", "request_id"}}`; sanitized
  422 (field loc/type only, no input values); generic 500 with catch-all handler.
- Request-ID middleware binds structlog context; security headers on every response;
  Origin check on cookie-authenticated refresh/logout as CSRF defense-in-depth.
- Log pipeline redaction of dangerous keys — pipeline-enforced, not convention-only.
- CI enforces lint/types, pip-audit, gitleaks, migrations-from-empty, full suite,
  and a standalone `tests/security` job. Branch protection should require the
  pipeline before merge.
- Log-based alerting signals to implement in production (Chapter 9): refresh reuse
  revocations, `access.denied` spikes, sustained 429s, `secret.revealed` volume
  anomalies, `unhandled_exception` rate, and audit chain verification failure.
  Schedule `scripts/verify_chain.py` per tenant on an interval via platform cron.

## Consequences

- Rate limits need tuning runbooks; false 429s are an availability cost.
- Redis becomes an operational dependency in every environment.
- The security suite is a merge gate: changing a guarantee means changing its test
  in the same PR, with review.
- API clients must parse the unified `error` object instead of FastAPI `detail`.

## References

- VaultLogBook Chapter 8 — Security hardening and the production pipeline
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — presentation owns HTTP mapping
