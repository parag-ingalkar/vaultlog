# VaultLog frontend

Next.js client for the VaultLog API. The app is the daily workspace for listing vaults, managing secrets, collaborating with teammates, and reviewing audit activity.

## Tech stack

| Layer | Choice |
|-------|--------|
| Framework | Next.js 16 (App Router) |
| UI | React 19 |
| Language | TypeScript |
| Styling | Tailwind CSS 4 |
| Data fetching | TanStack Query v5 |
| API types | openapi-typescript (generated from `api_contracts.json`) |
| Icons | lucide-react |
| Package manager | pnpm |

## Architecture

The frontend is organized by domain, with shared infrastructure in `lib/` and reusable UI in `components/`.

```text
app/                    # Next.js routes (App Router)
  (public)/             # Login, register, accept-invite
  (authenticated)/      # Vaults, team, audit, settings (behind AuthGuard)
  mfa/enroll/           # MFA enrollment flow
components/             # Shared UI primitives and cross-cutting components
domains/                # Feature modules (api, queries, mutations per domain)
  auth/                 # Session bootstrap, auth provider, login/register
  vaults/               # Vault list and detail
  secrets/              # Secret CRUD and reveal
  members/              # Team member list
  invitations/          # Invite creation and acceptance
  audit/                # Audit log display
  organization/         # Org metadata
hooks/                  # usePermissions, useStepUpHandler
lib/
  api/                  # HTTP client, generated schema, error parsing
  auth/                 # Token store, refresh scheduler, step-up cache
  query/                # TanStack Query client, keys, invalidation
  permissions.ts        # RBAC helpers (mirrors backend capabilities)
```

### Data flow

1. **API client** (`lib/api/client.ts`) — Typed fetch wrapper. Attaches the in-memory access token, handles proactive refresh, and retries on 401.
2. **TanStack Query** — Each domain exposes `api.ts` (raw calls), `queries.ts` (reads), and `mutations.ts` (writes). Query keys are centralized in `lib/query/keys.ts`.
3. **Auth provider** (`domains/auth/auth-provider.tsx`) — Bootstraps the session on load via refresh cookie, exposes `me` and server-derived `capabilities`.
4. **Capability guards** — `usePermissions()` and `CapabilityGuard` hide UI the user's role cannot access. The backend remains authoritative.

### Route groups

| Group | Guard | Pages |
|-------|-------|-------|
| `(public)` | None | Login, register, accept invitation |
| `(authenticated)` | `AuthGuard` + `AppShell` | Vaults, team, audit, settings |
| `mfa/enroll` | Auth required, MFA not yet enrolled | TOTP setup with QR code |

Navigation items in `AppShell` are filtered by capabilities — Team and Audit links appear only for users with the relevant permissions.

## Local development

### 1. Start the backend

From `backend/`:

```bash
docker compose up -d
uv run alembic upgrade head
uv run fastapi dev -e vaultlog.main:app
```

Ensure backend `CORS_ORIGINS` includes `http://localhost:3000` and `INVITE_BASE_URL=http://localhost:3000/accept-invite`.

### 2. Configure environment

```bash
cp .env.example .env.local
```

### 3. Install and run

```bash
pnpm install
pnpm dev
```

The app is at http://localhost:3000. By default the browser calls `/api/v1`, and Next.js proxies that prefix to `API_PROXY_TARGET` (`http://localhost:8000`).

## Environment variables

| Variable | Scope | Purpose |
|----------|-------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Build (inlined) | API prefix used by the browser. Prefer `/api/v1`. An absolute origin (e.g. `https://api.example.com/api/v1`) is allowed if listed in backend `CORS_ORIGINS`. |
| `API_PROXY_TARGET` | Server | FastAPI origin for Next.js rewrites of `/api/v1/*`. Required when the public API URL is relative. |

`NEXT_PUBLIC_*` values are baked in at `next build`. Changing the API host at container runtime only works if you built with a relative `/api/v1` prefix and set `API_PROXY_TARGET` for the running Next.js process.

Production build fails if `NEXT_PUBLIC_API_BASE_URL` is unset.

## Authentication and session

VaultLog uses a hybrid token model:

- **Access token** — Short-lived JWT held in memory only (`lib/auth/token-store.ts`). Never persisted to `localStorage` or `sessionStorage`.
- **Refresh token** — HttpOnly cookie set by the backend on login/MFA verify. The browser sends it automatically on `/auth/refresh` and `/auth/logout` via `credentials: "include"`.
- **Proactive refresh** — `refresh-scheduler.ts` refreshes the access token before expiry.
- **MFA challenge** — When MFA is enabled, login returns a challenge token instead of a session. The user completes TOTP verification before tokens are issued.
- **Step-up** — Destructive actions (delete vault/secret, remove member) trigger a modal (`step-up-modal.tsx`) that obtains a purpose-scoped step-up token and retries the request with `X-Step-Up-Token`.

On page load, `session-bootstrap.ts` calls `/auth/refresh` to restore the session silently.

## Permissions in the UI

Server-derived capabilities from `GET /auth/me` drive what the user can do:

| Capability | UI effect |
|------------|-----------|
| `can_create_vaults` | Create vault button, grant management |
| `can_write_secrets` | Create/edit/rotate secrets |
| `can_manage_members` | Remove team members |
| `can_manage_invitations` | Invite new users |
| `can_read_audit` | Audit log navigation and page |

Invitation rules (`lib/permissions.ts`):

- **Owners** can invite admins, members, and viewers.
- **Admins** can invite members and viewers only.
- Owners cannot be removed. Admins cannot remove other admins.

These mirror backend `PolicyService` rules; the API enforces authorization regardless of UI state.

## Secret handling

- Secret plaintext is fetched on demand via `POST .../reveal` and held in component state.
- Plaintext is dropped when navigating away from the secret detail page.
- Reveal, copy, and hide are explicit user actions — values are hidden by default.
- Reveal responses use `Cache-Control: no-store`.

## API type generation

Types are generated from the backend OpenAPI contract:

```bash
pnpm generate:api
```

This reads `../api_contracts.json` and writes `lib/api/schema.ts`. The command runs automatically before `pnpm build`.

## Scripts

```bash
pnpm dev          # Development server (http://localhost:3000)
pnpm lint         # ESLint (includes TanStack Query rules)
pnpm build        # Generate OpenAPI types + production build
pnpm start        # Serve the production build
pnpm generate:api # Regenerate types from api_contracts.json
```

## Production notes

- Serve the app over HTTPS and set backend `REFRESH_COOKIE_SECURE=true`.
- Same-origin `/api/v1` (reverse proxy or `API_PROXY_TARGET`) keeps the HttpOnly refresh cookie first-party.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) are set in `next.config.ts`.
- Access tokens stay in memory only; refresh tokens never enter JavaScript.

## Further reading

- [README.md](../README.md) — Application overview, roles, and RBAC matrix
- [backend/README.md](../backend/README.md) — API and security model
- [PRODUCT.md](../PRODUCT.md) — Design principles and brand personality
