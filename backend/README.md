# VaultLog backend

FastAPI service for VaultLog — a security-first, multi-tenant secrets manager. Each organization owns encrypted vaults containing secrets (API keys, tokens, credentials). The API handles authentication, authorization, envelope encryption, audit logging, and team collaboration.

## Tech stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.14+ |
| Framework | FastAPI (async) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Database | PostgreSQL 18 with Row-Level Security (RLS) |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Migrations | Alembic |
| Cache / rate limiting | Redis |
| Auth | RS256 JWT access tokens + opaque rotating refresh tokens (HttpOnly cookie) |
| Passwords | Argon2id |
| MFA | TOTP (RFC 6238) with encrypted seeds and recovery codes |
| Encryption | AES-256-GCM envelope encryption with per-tenant DEKs |
| Email | SMTP (MailHog locally) |
| Logging | structlog |

## Architecture

The backend follows domain-driven design with hexagonal boundaries. Dependencies point inward — the domain never imports FastAPI, SQLAlchemy, or Pydantic.

```text
HTTP request
   |
   v
Presentation   (routers, DTOs, middleware, exception → HTTP mapping)
   |
   v
Application    (use cases: open UoW, call domain service, commit)
   |
   v
Domain         (entities, domain services, ports, exceptions)
   |
   v
Infrastructure (SQLAlchemy, PostgreSQL, Argon2, JWT, Redis, SMTP)
```

Bounded contexts live under `src/vaultlog/domain/`:

- `identity` — registration, login, sessions, MFA
- `organizations` — members, invitations
- `vaults` — vault lifecycle and grants
- `secrets` — encrypted secret storage and reveal
- `access` — centralized `PolicyService` for all authorization
- `audit` — hash-chained append-only audit ledger

See [ARCHITECTURE.md](../ARCHITECTURE.md) for layer responsibilities and the feature checklist. Security decisions are recorded in `docs/adr/`.

### Database roles

Two connection paths enforce tenant isolation:

| UoW | DB role | Use |
|-----|---------|-----|
| `SqlAlchemyUnitOfWork` | `vaultlog_app` (NOBYPASSRLS) | All tenant-scoped data after authentication |
| `SqlAlchemyIdentityUnitOfWork` | `vaultlog_owner` (BYPASSRLS) | Pre-tenant auth: register, login, refresh, logout |

Tenant context is set via `SET LOCAL app.current_tenant` at transaction start. RLS policies are applied from idempotent scripts in `scripts/rls/policies/` (not embedded in Alembic revisions).

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose

## Local development

### 1. Start infrastructure

From `backend/`:

```bash
docker compose up -d
```

This starts PostgreSQL (port 5432), Redis (6379), and MailHog (SMTP 1025, UI http://localhost:8025).

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and replace the `CHANGE_ME` placeholders for `MFA_KEK_B64` and `MASTER_KEY_B64` with 32-byte base64-encoded keys:

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Generate JWT signing keys:

```bash
mkdir -p keys
openssl genrsa -out keys/jwt-private.pem 2048
openssl rsa -in keys/jwt-private.pem -pubout -out keys/jwt-public.pem
chmod 600 keys/jwt-private.pem
```

### 3. Install dependencies and migrate

```bash
uv sync
uv run alembic upgrade head
```

RLS policies are applied automatically after `alembic upgrade`. To re-apply after editing a policy file:

```bash
uv run python -m scripts.rls.apply
```

### 4. Run the API

```bash
uv run fastapi dev -e vaultlog.main:app
```

The API is at http://localhost:8000. OpenAPI docs are at http://localhost:8000/docs (disabled in production).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | `local`, `test`, `staging`, or `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `http://localhost:3000`) |
| `REDIS_URL` | Redis connection for rate limiting |
| `DATABASE_*` | Application DB connection (`vaultlog_app` role) |
| `MIGRATION_DATABASE_*` | Schema owner connection for Alembic (`vaultlog_owner` role) |
| `JWT_*` | RS256 key paths, issuer, audience, TTLs |
| `REFRESH_COOKIE_SECURE` | Set `false` locally, `true` in production |
| `MFA_KEK_B64` | 32-byte base64 key for encrypting TOTP seeds at rest |
| `MASTER_KEY_B64` | 32-byte base64 KEK for envelope encryption (separate from MFA key) |
| `SMTP_*` | Email delivery for invitations |
| `INVITE_BASE_URL` | Frontend URL for invitation links |

See [.env.example](.env.example) for the full list with defaults.

## API overview

All routes are prefixed with `/api/v1`.

| Router | Endpoints |
|--------|-----------|
| `health` | `GET /health` |
| `auth` | Register, login, refresh, logout, `GET /me`, MFA enroll/verify/confirm/remove |
| `organization` | `GET /organization` |
| `vaults` | CRUD vaults, list/manage grants |
| `secrets` | Create, list, reveal, rotate, delete secrets (scoped to a vault) |
| `audit` | `GET /audit` (filtered event log) |
| `members` | List members, remove member (step-up required) |
| `invitations` | Create, list, revoke, preview, accept invitations |

Tenant-scoped routes (`vaults`, `secrets`, `audit`) require MFA enrollment for organization owners.

Sensitive operations (vault/secret deletion, member removal, MFA changes) require a step-up token in the `X-Step-Up-Token` header.

The OpenAPI contract is exported to [`api_contracts.json`](../api_contracts.json) at the repo root for frontend type generation.

## Security model

- **Passwords:** Argon2id, 12–128 character policy, timing-equalized verification.
- **Access tokens:** RS256 JWT, short TTL (~10 min), claims `sub`, `tid`, `sid`, `amr`.
- **Refresh tokens:** Opaque, SHA-256 at rest, rotated on every use; reuse detection revokes the session family.
- **Cookies:** HttpOnly refresh cookie scoped to `/api/v1/auth`, SameSite=Lax.
- **Multi-tenancy:** Shared PostgreSQL + RLS on tenant-owned tables; JWT `tid` validated at mint time.
- **Encryption:** Per-tenant versioned DEKs wrapped by a KEK; secret plaintext only in reveal responses.
- **Audit:** Hash-chained append-only ledger per tenant; app role cannot UPDATE/DELETE audit rows.
- **Rate limiting:** Redis-backed counters on auth and invitation endpoints.

## Testing

```bash
# Unit tests (no database)
uv run pytest tests/unit -v

# Integration tests (uses vaultlog_test database, never vaultlog)
uv run pytest tests/integration -v

# Security / hardening tests
uv run pytest tests/security -v

# All tests
uv run pytest
```

### Linting and type checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Project layout

```text
backend/
├── alembic/                  # Schema migrations
├── compose.yml               # PostgreSQL, Redis, MailHog
├── docker/postgres/init.sql  # DB roles and test database bootstrap
├── docs/
│   ├── adr/                  # Architecture decision records
│   └── migration-checklist.md
├── scripts/
│   ├── rls/                  # RLS policy scripts and apply tooling
│   └── verify_chain.py       # Audit chain integrity verification
├── src/vaultlog/
│   ├── application/          # Use cases and application ports
│   ├── domain/               # Business logic by bounded context
│   ├── infrastructure/       # DB, security, email adapters
│   ├── presentation/         # FastAPI routers, middleware, dependencies
│   ├── shared/               # Config and logging
│   └── main.py               # App factory
└── tests/
    ├── unit/
    ├── integration/
    └── security/
```

## Adding a tenant-owned table

1. Autogenerate an Alembic migration with schema + `GRANT` to `vaultlog_app` (no RLS in the revision).
2. `uv run python -m scripts.rls.new_policy <table>`
3. Add the table to `TENANT_TABLES` in `scripts/rls/apply.py`.
4. `uv run alembic upgrade head`.

See [docs/migration-checklist.md](docs/migration-checklist.md) and [scripts/rls/README.md](scripts/rls/README.md).

## Further reading

- [ARCHITECTURE.md](../ARCHITECTURE.md) — DDD layers, ports/adapters, exception flow
- [VaultLogBook.md](../VaultLogBook.md) — Security design tutorial (chapter by chapter)
- [PRODUCT.md](../PRODUCT.md) — Product purpose and design principles
- `docs/adr/` — Immutable security and architecture decisions
