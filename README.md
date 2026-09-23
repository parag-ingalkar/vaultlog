# VaultLog

VaultLog is a multi-tenant secrets manager for teams. Each organization owns encrypted vaults containing secrets — API keys, tokens, credentials — with role-based access control, MFA, step-up authentication, and a tamper-evident audit ledger.

The repository is a monorepo:

| Directory | Description |
|-----------|-------------|
| [`backend/`](backend/) | FastAPI API — auth, encryption, RLS, audit |
| [`frontend/`](frontend/) | Next.js web client |
| [`api_contracts.json`](api_contracts.json) | OpenAPI contract shared between backend and frontend |

## What it does

- **Organizations** — Each user belongs to exactly one organization. Founding owners self-register; everyone else joins via email invitation.
- **Vaults** — Logical containers for secrets within an organization.
- **Secrets** — Encrypted at rest with per-tenant envelope encryption. Values are hidden by default and revealed on demand.
- **Team collaboration** — Invite teammates with role assignments. Owners and admins manage membership.
- **Audit log** — Hash-chained, append-only event ledger per tenant. Records vault/secret access, mutations, and authorization denials.
- **MFA** — TOTP-based two-factor authentication. Required for organization owners before accessing tenant APIs.
- **Step-up authentication** — Sensitive operations (deletions, member removal) require fresh MFA proof within the current session.

## Roles

VaultLog uses four organization roles. Every user has exactly one role in their organization.

| Role | Description |
|------|-------------|
| **Owner** | Created the organization at registration. Full administrative access. Must enroll MFA before using vault APIs. Can invite any role including admins. |
| **Admin** | Full administrative access except cannot remove other admins or the owner. Can invite members and viewers. |
| **Member** | Can read and write secrets in all vaults. Cannot create vaults, manage grants, view audit logs, or manage team members. |
| **Viewer** | Read-only access to secrets (metadata and reveal). Cannot write, delete, or manage anything. |

There is no organization switching — a user's JWT `tid` claim identifies their single organization unambiguously.

## RBAC rules

Authorization uses two axes:

1. **Organization role** — Baseline capabilities (create vaults, manage team, read audit).
2. **Vault grants** — Fine-grained read/write/admin permissions on specific vaults. Owner and admin APIs can assign grants per membership. Members and viewers receive org-wide vault access by role without needing individual grants.

All authorization decisions flow through a single `PolicyService` in the backend. The frontend mirrors capabilities from `GET /auth/me` for UI gating, but the API is always authoritative.

### Organization-level permissions

| Action | Owner | Admin | Member | Viewer |
|--------|:-----:|:-----:|:------:|:------:|
| List vaults | ✓ | ✓ | ✓ | ✓ |
| Create vault | ✓ | ✓ | | |
| Update vault | ✓ | ✓ | | |
| Delete vault | ✓ | ✓ | | |
| Manage vault grants | ✓ | ✓ | | |
| Invite members | ✓ | ✓ | | |
| Remove members | ✓ | ✓* | | |
| Read audit log | ✓ | ✓ | | |

\* Admins cannot remove other admins or the owner. Users cannot remove themselves.

### Vault-level permissions (by role)

Owner and admin receive synthetic vault-admin access on every vault. Members and viewers receive org-wide access without per-vault grant rows.

| Action | Owner | Admin | Member | Viewer |
|--------|:-----:|:-----:|:------:|:------:|
| Read secret metadata | ✓ | ✓ | ✓ | ✓ |
| Reveal secret value | ✓ | ✓ | ✓ | ✓ |
| Write / rotate secrets | ✓ | ✓ | ✓ | |
| Delete secrets | ✓ | ✓ | ✓ | |

Viewers are hard-capped at read access regardless of any grant data in the database.

### Vault grants (fine-grained)

Owners and admins can assign per-membership vault grants with three levels:

| Grant | Allows |
|-------|--------|
| `read` | Read metadata and reveal secret values |
| `write` | Read + create and rotate secrets |
| `admin` | Write + delete secrets |

Grant management is optional for standard onboarding — members and viewers already receive org-wide vault access by role. The grant APIs exist for owner/admin fine-grained compartmentalization when the product needs per-vault restrictions beyond the default role behavior.

### Invitation rules

| Inviter role | Can invite |
|--------------|------------|
| Owner | Admin, member, viewer |
| Admin | Member, viewer |

Invitations expire after 7 days. Pending invitations are unique per `(organization, email)`.

## Authentication flows

### Owner registration

1. `POST /auth/register` — Creates user, organization, and owner membership.
2. MFA enrollment required before vault/secret/audit APIs are accessible.
3. Login → MFA verify (if enabled) → access token + refresh cookie.

### Member onboarding

1. Owner or admin sends an invitation email.
2. Invitee visits `/accept-invite` and accepts via `POST /invitations/accept`.
3. Normal login flow (with MFA if the user has enrolled).

### Step-up authentication

These actions require a purpose-scoped step-up token (`X-Step-Up-Token` header) in addition to the access token:

- Delete vault or secret
- Remove a team member
- MFA enrollment changes

The frontend presents a TOTP prompt modal and retries the failed request with the step-up token.

## Security highlights

| Concern | Approach |
|---------|----------|
| Tenant isolation | PostgreSQL RLS on all tenant-owned tables |
| Passwords | Argon2id with timing-equalized verification |
| Sessions | RS256 JWT (short TTL) + opaque rotating refresh tokens |
| Encryption | AES-256-GCM envelope encryption with per-tenant DEKs |
| MFA | TOTP with encrypted seeds, recovery codes, challenge tokens |
| Audit | Hash-chained append-only ledger; app role cannot modify events |
| Rate limiting | Redis-backed counters on auth and invitation endpoints |

## Quick start

### Backend

```bash
cd backend
docker compose up -d
cp .env.example .env
# Generate JWT keys and encryption keys (see backend/README.md)
uv sync
uv run alembic upgrade head
uv run fastapi dev -e vaultlog.main:app
```

API: http://localhost:8000 — Docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

App: http://localhost:3000

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for full setup details, environment variables, and development workflows.

## Documentation

| Document | Contents |
|----------|----------|
| [backend/README.md](backend/README.md) | Backend setup, API overview, testing, project layout |
| [frontend/README.md](frontend/README.md) | Frontend architecture, auth model, scripts |
| [ARCHITECTURE.md](ARCHITECTURE.md) | DDD layers, ports/adapters, exception flow |
| [VaultLogBook.md](VaultLogBook.md) | Security design tutorial (chapter by chapter) |
| [PRODUCT.md](PRODUCT.md) | Product purpose, users, design principles |
| [backend/docs/adr/](backend/docs/adr/) | Architecture decision records |

## License

Private repository. All rights reserved.
