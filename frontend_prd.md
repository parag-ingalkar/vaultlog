# VaultLog Frontend PRD — Drop-In Integration Plan

**Version:** 1.0
**Audience:** Frontend implementation agents (e.g. GLM5.2) and human developers
**Backend status:** Feature-complete for core workflows; OpenAPI at `/docs` and `/openapi.json` (local only)

This document describes what the VaultLog backend provides, how the frontend should behave, and how to wire against the API **without embedding request/response schemas**. Generate exact contracts from the backend Swagger/OpenAPI spec.

---

## 1. Product summary

VaultLog is a **multi-tenant secrets manager** for teams. Each **organization (tenant)** owns encrypted **vaults** containing **secrets** (credentials, API keys, tokens). Access is governed by **organization roles** and optional **per-vault grants**. Security is central: **TOTP MFA**, **step-up authentication** for destructive actions, **hash-chained audit logs**, and **envelope encryption** per tenant.

The frontend is a **drop-in SPA** that talks only to the existing REST API. No backend changes are required for core flows. After configuring the API base URL and CORS origin, the app should work end-to-end against a running backend (`backend/compose.yml` stack).

### What “multi-tenant” means in this product

| Concept | Behavior |
|---------|----------|
| Tenant | One **organization**; `tenant_id` in the JWT equals `organization.id` |
| User ↔ org | **Exactly one organization per user** (database-enforced) |
| Org switching | **Not supported** — no org selector, no `X-Tenant-ID` header |
| Tenant context | Embedded in the access token at login/refresh; server applies RLS |

The UI should feel like a **single-org workspace** (org name in shell/header), not a platform where users pick tenants.

---

## 2. Backend capabilities (what exists today)

### 2.1 Bounded contexts & API surface

All routes are under **`/api/v1`**. Grouped by feature:

| Area | Prefix | Purpose |
|------|--------|---------|
| Health | `/health` | Liveness (`{ "status": "ok" }`) |
| Auth | `/auth` | Register, login, refresh, logout, session profile, MFA enroll/confirm/verify/disable, step-up |
| Organization | `/organization` | Current org metadata + caller role |
| Members | `/members` | List members; remove member (step-up) |
| Invitations | `/invitations` | Create/list/revoke invites; public preview + accept |
| Vaults | `/vaults` | CRUD vaults; list/manage per-vault grants |
| Secrets | `/vaults/{vault_id}/secrets` | CRUD metadata; reveal plaintext; rotate value |
| Audit | `/audit-events` | Filterable, paginated audit ledger (owner/admin) |

### 2.2 Domain entities & relationships

```
User ──(1 membership)──► Organization
Organization ──► Vault ──► Secret ──► SecretVersion (versioned values)
Organization ──► Invitation (pending email invites)
Organization ──► AuditEvent (append-only ledger)
Vault ──► VaultGrant (optional fine-grained access for a membership)
User ──► AuthSession ──► RefreshToken (rotating, cookie-bound)
User ──► TotpSecret + RecoveryCode (optional MFA)
```

**Soft deletes:** Vaults and secrets use `deleted_at`; they do not appear in list endpoints.

**Encryption:** Secret values are encrypted at rest with per-tenant keys. Plaintext only appears in the **reveal** response. Audit metadata never contains secret values.

### 2.3 Roles & permissions (UI gating source)

**Organization roles:** `owner`, `admin`, `member`, `viewer`

| Capability | owner | admin | member | viewer |
|------------|-------|-------|--------|--------|
| List vaults / secret metadata | ✓ | ✓ | ✓ | ✓ |
| Create vault | ✓ | ✓ | ✗ | ✗ |
| Update/delete vault | ✓ | ✓ | ✗ | ✗ |
| Create / rotate secrets | ✓ | ✓ | ✓ | ✗ |
| Reveal secrets | ✓ | ✓ | ✓ | ✓ |
| Delete secrets | ✓ | ✓ | ✓ | ✗ |
| Invite members | ✓ | ✓* | ✗ | ✗ |
| Remove members | ✓ | ✓** | ✗ | ✗ |
| View audit log | ✓ | ✓ | ✗ | ✗ |
| Manage vault grants | ✓ | ✓ | ✗ | ✗ |

\* Admins cannot invite `admin` role (owners only).
\** Admins cannot remove owners or other admins.

**Vault grant permissions** (when managing explicit grants): `read` < `write` < `admin`. Grants are **supplementary** — members and viewers already receive org-wide vault access by role. Grant UI is for owner/admin fine-tuning, not required for onboarding.

**Authoritative UI flags:** `GET /auth/me` returns a `capabilities` object:

- `can_create_vaults`
- `can_manage_members`
- `can_manage_invitations`
- `can_read_audit`

Prefer these booleans for nav and button visibility; they mirror server policy.

### 2.4 Security features the frontend must implement

| Feature | Backend behavior | Frontend responsibility |
|---------|------------------|-------------------------|
| Access token | JWT in `Authorization: Bearer`, ~10 min TTL | Store in memory; attach to protected calls |
| Refresh token | HttpOnly cookie `vaultlog_refresh`, path `/api/v1/auth` | `credentials: 'include'` on refresh/logout only |
| MFA at login | Login may return MFA challenge instead of token | Branch UI to TOTP/recovery code step |
| Owner MFA gate | Owners without MFA get `403 mfa_enrollment_required` on vault/secret/audit/member/invite routes | Force MFA enrollment wizard before main app |
| Step-up MFA | Destructive ops need `X-Step-Up-Token` header | Modal: TOTP → step-up token → retry delete |
| Secret reveal | `POST` reveal endpoint, `Cache-Control: no-store` | Never cache; clear from UI on navigation |
| CSRF on cookie routes | Refresh/logout validate `Origin` vs `CORS_ORIGINS` | Same-origin SPA or correct dev origin |
| Rate limits | `429` with `Retry-After` (seconds) | Show cooldown UI; disable retry button |

### 2.5 Step-up purposes (must match exactly)

Request step-up via `POST /auth/step-up/verify` with `purpose` string, then send token in `X-Step-Up-Token`:

| Purpose | Used when |
|---------|-----------|
| `step-up:delete-vault` | `DELETE /vaults/{id}` |
| `step-up:delete-secret` | `DELETE /vaults/{vault_id}/secrets/{id}` |
| `step-up:remove-member` | `DELETE /members/{membership_id}` |
| `step-up:manage-mfa` | `DELETE /auth/mfa` |
| `step-up:rotate-keys` | Defined but **no API endpoint uses it yet** |

Step-up tokens expire in ~300 seconds. Cache per purpose in the client session to avoid re-prompting within the TTL.

### 2.6 Audit vocabulary (for audit log UI)

**Actions** (filter param `action`):
`vault.created`, `vault.updated`, `vault.deleted`, `grant.created`, `grant.updated`, `grant.revoked`, `secret.created`, `secret.revealed`, `secret.rotated`, `secret.deleted`, `key.rotated`, `member.invited`, `member.removed`, `member.role_changed`, `mfa.enabled`, `mfa.disabled`, `stepup.issued`, `access.denied`

**Outcomes:** `success`, `failure`, `denied`

Only **audit events** support pagination (`limit`, `before_sequence` cursor, max 500). Other lists return full arrays.

### 2.7 Not implemented on backend (do not build UI that depends on these)

- Password reset / forgot password
- Email verification
- Organization switching or multi-org membership
- User profile edit (email change, etc.)
- Key rotation API (step-up purpose exists but no route)
- Pagination on vaults, secrets, members, invitations lists

---

## 3. Drop-in integration requirements

These are **non-negotiable** for a frontend that works immediately after wiring.

### 3.1 Environment variables (frontend)

| Variable | Example | Notes |
|----------|---------|-------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | All API paths are relative to this |
| Dev server origin | `http://localhost:5173` | Must match backend `CORS_ORIGINS` |

Backend defaults (from `backend/.env.example`) the frontend team should align with:

```
CORS_ORIGINS=http://localhost:5173
ACCESS_TOKEN_TTL_SECONDS=600
REFRESH_TOKEN_TTL_DAYS=30
REFRESH_COOKIE_SECURE=false          # true in production (HTTPS required)
INVITE_BASE_URL=http://localhost:5173/accept-invite
STEP_UP_TOKEN_TTL_SECONDS=300
```

Invitation emails link to `{INVITE_BASE_URL}?token={raw_token}`. The frontend **must** expose route **`/accept-invite`** with query param **`token`**.

### 3.2 API client architecture

Implement a thin HTTP layer (fetch or axios) with:

1. **Base URL** from env.
2. **JSON** `Content-Type` on bodies.
3. **Bearer injection** from in-memory access token store.
4. **Optional** `X-Request-ID` (echoed in responses for support).
5. **`credentials: 'include'`** only for:
   - `POST /auth/refresh`
   - `POST /auth/logout`
6. **401 interceptor:**
   - On protected call → try `POST /auth/refresh` once (with credentials).
   - Success → update access token, retry original request.
   - Failure → clear session, redirect to login.
7. **Proactive refresh:** Schedule refresh ~1–2 minutes before `expires_in` from login/refresh responses.
8. **Error normalizer:** Parse `{ "error": { "code", "message", "request_id", "fields?" } }`.

**Do not** store refresh tokens in JS — they live only in the HttpOnly cookie.

### 3.3 CORS & cookies

- Backend `allow_credentials: true`.
- Allowed headers: `Authorization`, `Content-Type`, `X-Request-ID`, `X-Step-Up-Token`.
- Local dev: API on port 8000, frontend on 5173 is the expected setup (`backend/compose.yml` + Vite).
- Production: HTTPS + `REFRESH_COOKIE_SECURE=true`; frontend must be served from an origin listed in `CORS_ORIGINS`.

### 3.4 Session bootstrap (app load)

```
1. If access token in memory → GET /auth/me
2. Else → POST /auth/refresh (credentials: include)
   → success: store token, GET /auth/me
   → failure: show public routes (login, register, accept-invite)
3. From /auth/me:
   - If mfa_enrollment_required && role === owner → MFA enrollment flow (block main app)
   - Else → render app shell with capabilities-driven nav
```

`/auth/me` is the **single source of truth** for: user email, org name/id, role, MFA state, session id, `amr`, and capabilities.

### 3.5 Route map (minimum viable)

| Route | Auth | Purpose |
|-------|------|---------|
| `/login` | Public | Email + password; MFA branch |
| `/register` | Public | Founder signup (creates user + org) |
| `/accept-invite` | Public | `?token=` — preview + accept + redirect to login |
| `/mfa/enroll` | Authenticated | Owner MFA setup (QR + confirm + recovery codes) |
| `/` or `/vaults` | Authenticated | Vault list (default landing) |
| `/vaults/:vaultId` | Authenticated | Vault detail + secrets list |
| `/vaults/:vaultId/secrets/:secretId` | Authenticated | Secret detail (reveal, rotate, delete) |
| `/vaults/:vaultId/grants` | Authenticated | Grant management (owner/admin) |
| `/team` | Authenticated | Members + invitations (owner/admin) |
| `/audit` | Authenticated | Audit log (owner/admin) |
| `/settings` | Authenticated | Org info, MFA status, logout |

Exact path naming is flexible; **`/accept-invite`** with `token` query param is required for email links.

### 3.6 Drop-in acceptance criteria

The frontend is “wired and working” when:

- [ ] Register → login → owner sees MFA enrollment gate → enroll → main app
- [ ] Owner creates vault → creates secret → reveals value → rotates → deletes (with step-up)
- [ ] Owner invites member → email in MailHog → accept-invite flow → member logs in → sees vaults by role
- [ ] Viewer can reveal but cannot create/rotate/delete secrets
- [ ] Token refresh works across 10+ minutes without re-login
- [ ] Logout clears session and cookie
- [ ] Audit log loads with pagination for owner/admin
- [ ] `403 mfa_enrollment_required` never appears as a raw error for owners who completed enrollment
- [ ] Secret values never persist in localStorage/sessionStorage

---

## 4. How to use the API contracts (without embedding them)

1. **Generate types and clients** from OpenAPI (`http://localhost:8000/openapi.json` when `ENVIRONMENT=local`).
2. **Map each screen** to endpoint(s) listed in Section 5 workflows — one OpenAPI tag per area (`auth`, `vaults`, `secrets`, etc.).
3. **Status codes:**
   - `200` / `201` — success with JSON body
   - `204` — success, no body (logout, deletes, grant mutations, invite accept)
4. **Validation** — `422` with `error.code === "validation_failed"` and `error.fields[]` (`loc`, `type`). Show field-level messages in forms.
5. **Business errors** — use `error.code` for branching (see Section 6).
6. **Datetime** — ISO 8601 strings in JSON.
7. **IDs** — UUID strings in JSON and path parameters.
8. **Field constraints** (for form validation, mirror server):
   - Password: 12–128 characters
   - Names: 1–200 characters
   - Descriptions: max 1000 characters
   - Secret values: max 10,000 characters
   - TOTP code: 6–8 chars at step-up; 6–20 at MFA login (recovery codes allowed)
9. **Invite roles** — only `admin`, `member`, `viewer` (not `owner`).
10. **Secret reveal** — `POST` (not GET); optional `?version=N` for historical version.

---

## 5. Core workflows (end-to-end)

Each workflow lists **user steps**, **API sequence**, and **UI notes**. Refer to OpenAPI for exact payloads.

### 5.1 Founder registration & first login

**Actors:** New user becoming organization owner.

| Step | User action | API | UI notes |
|------|-------------|-----|----------|
| 1 | Open register page | — | Fields: email, password, organization name |
| 2 | Submit registration | `POST /auth/register` | Success returns **only** `user_id` — **no tokens** |
| 3 | Redirect to login | — | Explain account created; must sign in |
| 4 | Sign in | `POST /auth/login` | Sets refresh cookie on success |
| 5 | Load session | `GET /auth/me` | `role: owner`, `mfa_enrollment_required: true` |
| 6 | MFA enrollment | See §5.2 | **Block** vault/team/audit until complete |

**Errors:** `409 registration_conflict` if email exists — generic message (do not confirm email enumeration).

### 5.2 MFA enrollment (owners — required)

**Also used when** any owner hits protected routes before MFA: server returns `403 mfa_enrollment_required`.

| Step | User action | API | UI notes |
|------|-------------|-----|----------|
| 1 | Start enrollment | `POST /auth/mfa/enroll` | Response includes `provisioning_uri` (`otpauth://...`) |
| 2 | Scan QR / enter secret in authenticator app | — | Display QR from provisioning URI |
| 3 | Confirm with 6-digit code | `POST /auth/mfa/confirm` | Body: TOTP code |
| 4 | Save recovery codes | — | Response: `recovery_codes[]` — **show once**, copy/download UX |
| 5 | Refresh session | `GET /auth/me` | `mfa_enabled: true`, `mfa_enrollment_required: false` |

**Errors:** `400 mfa_enrollment_failed` on bad code during confirm.

### 5.3 Login (password + optional MFA)

| Step | User action | API | UI notes |
|------|-------------|-----|----------|
| 1 | Enter email + password | `POST /auth/login` | — |
| 2a | No MFA | Response: access token + `expires_in` | Navigate to app |
| 2b | MFA enabled | Response: `mfa_required`, `challenge_token` | Show MFA code field |
| 3 | Submit TOTP or recovery code | `POST /auth/mfa/verify` | Sets refresh cookie; returns access token |
| 4 | Load session | `GET /auth/me` | Drive nav from `capabilities` |

**Errors:** `401 authentication_failed` / `401 mfa_verification_failed` — generic “invalid credentials” style messaging.

### 5.4 Session refresh & logout

| Action | API | UI notes |
|--------|-----|----------|
| Refresh | `POST /auth/refresh` + credentials | On 401 retry path; proactive timer from `expires_in` |
| Logout | `POST /auth/logout` + credentials | Clear in-memory token; redirect to login |
| Invalid refresh | `401` + cookie cleared | Treat as logged out |

**Errors:** `403 csrf_origin_mismatch` on refresh/logout if `Origin` header wrong — fix dev proxy/origin config.

### 5.5 Invitation flow (invited member)

**Actors:** Owner/admin invites; new or existing user accepts.

**Invite creation (owner/admin):**

| Step | User action | API | UI notes |
|------|-------------|-----|----------|
| 1 | Enter email + role | `POST /invitations` | Roles: admin, member, viewer |
| 2 | — | — | Email sent with link to `/accept-invite?token=...` |
| 3 | View pending | `GET /invitations` | List with expiry |
| 4 | Revoke | `DELETE /invitations/{id}` | — |

**Accept invite (public):**

| Step | User action | API | UI notes |
|------|-------------|-----|----------|
| 1 | Open link from email | `GET /invitations/preview?token=` | Show org name, role, masked email |
| 2 | Set password (12+ chars) | `POST /invitations/accept` | Returns `204` — **no auto-login** |
| 3 | Redirect to login | — | User signs in separately |
| 4 | Sign in | `POST /auth/login` | MFA if already enabled on account |

**Edge cases:**

- Existing user accepting: password must match their current account password.
- `404 invitation_not_found` — invalid/expired token; friendly error page.
- New user: accept creates account + membership in invite org.

### 5.6 Vault management

| Action | API | Who | UI notes |
|--------|-----|-----|----------|
| List vaults | `GET /vaults` | All roles | Default landing; empty state with CTA if `can_create_vaults` |
| Create vault | `POST /vaults` | owner, admin | Name + optional description |
| View vault | `GET /vaults/{id}` | All with access | Header: name, description, created_at |
| Update vault | `PATCH /vaults/{id}` | owner, admin | Name/description |
| Delete vault | `DELETE /vaults/{id}` | owner, admin | **Step-up required** (§5.10) |

Vault names are unique per organization.

### 5.7 Secret management

| Action | API | Who | UI notes |
|--------|-----|-----|----------|
| List secrets (metadata only) | `GET /vaults/{vault_id}/secrets` | All with vault access | No values in list |
| Create secret | `POST /vaults/{vault_id}/secrets` | owner, admin, member | name, value, optional description |
| Reveal plaintext | `POST /vaults/{vault_id}/secrets/{id}/reveal` | All except denied by role | Optional `?version=N`; show in masked/reveal toggle |
| Rotate value | `POST /vaults/{vault_id}/secrets/{id}/rotate` | owner, admin, member | Body: new `value`; `current_version` increments |
| Delete secret | `DELETE .../secrets/{id}` | owner, admin, member | **Step-up required** |

**Security UX for secrets:**

- Reveal is a deliberate action (button), not automatic on page load.
- Clear revealed values when leaving the view or after timeout.
- Copy-to-clipboard with brief visibility.
- Rate limit: 100 reveals / 5 min per user — handle `429`.

**Errors:** `409 secret_conflict` duplicate name in vault.

### 5.8 Vault grants (optional admin UI)

For owner/admin fine-grained access beyond org-wide role defaults.

| Action | API | UI notes |
|--------|-----|----------|
| List grants | `GET /vaults/{vault_id}/grants` | Shows **explicit** grants only |
| Upsert grant | `POST /vaults/{vault_id}/grants` | `membership_id` + `permission` (read/write/admin) |
| Revoke grant | `DELETE /vaults/{vault_id}/grants/{membership_id}` | — |

Use `GET /members` to populate membership picker. Grant UI is secondary; members/viewers work without grants.

### 5.9 Team management

| Action | API | Who | UI notes |
|--------|-----|-----|----------|
| List members | `GET /members` | owner, admin | membership_id needed for remove/grants |
| Remove member | `DELETE /members/{membership_id}` | owner, admin | **Step-up**; cannot remove self or owner |

Combine members + invitations on a **Team** screen with two tabs or sections.

### 5.10 Step-up authentication (destructive actions)

**Pattern for all sensitive deletes:**

```
1. User clicks Delete (vault, secret, member, or disable MFA)
2. Show step-up modal: “Confirm with your authenticator”
3. POST /auth/step-up/verify { code, purpose }
   → { step_up_token, expires_in }
4. Retry original DELETE with header X-Step-Up-Token: <token>
5. On success, close modal and refresh list
```

| Action | purpose value |
|--------|----------------|
| Delete vault | `step-up:delete-vault` |
| Delete secret | `step-up:delete-secret` |
| Remove member | `step-up:remove-member` |
| Disable MFA | `step-up:manage-mfa` |

**Errors:**

- `403 step_up_required` — missing/invalid/expired token → re-prompt
- `401 mfa_verification_failed` — wrong code in step-up modal

Cache `step_up_token` per purpose until `expires_in` elapses to allow batch deletes without re-prompting.

### 5.11 Disable MFA

| Step | API | UI notes |
|------|-----|----------|
| 1 | Step-up with `step-up:manage-mfa` | `POST /auth/step-up/verify` |
| 2 | Disable | `DELETE /auth/mfa` + `X-Step-Up-Token` |

Owners who disable MFA will be blocked from tenant APIs again until re-enrollment.

### 5.12 Audit log

| Action | API | Who | UI notes |
|--------|-----|-----|----------|
| List events | `GET /audit-events` | owner, admin | Query: `limit`, `before_sequence`, `action`, `target_id` |

**Pagination UX:** Cursor-based — use lowest `sequence` from batch as next `before_sequence`. Default `limit=100`, max 500.

Display: timestamp, actor, action, outcome, target type/id, metadata (never secret values).

### 5.13 Organization context

| Action | API | UI notes |
|--------|-----|----------|
| Org summary | `GET /organization` | `id`, `name`, `caller_role` |

Also available via `/auth/me.organization`. Use for header branding and settings page.

---

## 6. Error handling reference

Standard envelope:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "uuid-or-null"
  }
}
```

Validation (`422`):

```json
{
  "error": {
    "code": "validation_failed",
    "fields": [{ "loc": ["body", "password"], "type": "string_too_short" }],
    "request_id": "..."
  }
}
```

| HTTP | code | Frontend behavior |
|------|------|-------------------|
| 400 | `password_policy_violation` | Password field hint (12–128 chars) |
| 400 | `mfa_enrollment_failed` | Retry TOTP on enrollment |
| 400 | `invitation_failed` | Generic invite error |
| 401 | `authentication_failed` | Login failed / session expired |
| 401 | `mfa_verification_failed` | Retry MFA code |
| 403 | `forbidden` | Hide action or show “access denied” |
| 403 | `step_up_required` | Open step-up modal |
| 403 | `mfa_enrollment_required` | Redirect owner to MFA enrollment |
| 403 | `csrf_origin_mismatch` | Dev config issue — check origin |
| 404 | `not_found` | Resource missing or deleted |
| 404 | `invitation_not_found` | Invalid invite link page |
| 404 | `member_not_found` | Stale member list — refresh |
| 409 | `registration_conflict` | Registration error (generic) |
| 409 | `member_conflict` | Cannot remove self/owner |
| 409 | `secret_conflict` | Duplicate secret name |
| 422 | `validation_failed` | Field-level form errors |
| 429 | `http_429` | Show `Retry-After` countdown |
| 500+ | `internal_error`, etc. | Generic error + optional `request_id` for support |

**Security:** Do not infer “email already registered” from status codes in auth flows.

---

## 7. Recommended frontend architecture (for implementation agent)

This section guides the downstream implementation plan; not prescriptive on framework.

### 7.1 Suggested stack (align with backend dev defaults)

- **Vite + React** (or Vue/Svelte) on port **5173**
- **TypeScript** with OpenAPI-generated types
- **Router** for routes in §3.5
- **State:** lightweight store for auth session + capabilities; no secret values in global state longer than needed
- **Forms:** client validation matching server constraints

### 7.2 Module boundaries

| Module | Responsibility |
|--------|----------------|
| `api/client` | HTTP layer, interceptors, error parser |
| `api/auth` | Token store, refresh scheduler, step-up cache |
| `features/auth` | Login, register, MFA flows |
| `features/vaults` | Vault CRUD, grants |
| `features/secrets` | List, reveal, rotate, delete |
| `features/team` | Members, invitations, accept-invite |
| `features/audit` | Paginated audit viewer |
| `shell` | Layout, nav from capabilities, org header |

### 7.3 Capability-driven navigation

```
Nav items (example):
- Vaults          → always (authenticated, post-MFA-gate)
- Team            → capabilities.can_manage_members || can_manage_invitations
- Audit           → capabilities.can_read_audit
- Settings        → always (MFA status, logout)
```

### 7.4 Loading & empty states

| Screen | Empty state |
|--------|-------------|
| Vault list | “No vaults yet” + create button if allowed |
| Secret list | “No secrets in this vault” + create button if allowed |
| Team | “No pending invitations” / single-member org |
| Audit | “No events yet” |

### 7.5 Local development workflow

1. Start backend: `docker compose up` in `backend/` (API 8000, Postgres, Redis, MailHog 8025).
2. Start frontend on 5173 with `VITE_API_BASE_URL=http://localhost:8000/api/v1`.
3. View invitation emails at MailHog UI (`http://localhost:8025`).
4. OpenAPI docs at `http://localhost:8000/docs` for contract generation.

---

## 8. Security & compliance UX checklist

- [ ] Access token only in memory (not localStorage)
- [ ] No secret values in persistent storage or URL query params
- [ ] Reveal responses not cached by browser (respect `Cache-Control: no-store`)
- [ ] Step-up modal for all destructive actions
- [ ] Recovery codes shown once with strong warning
- [ ] Logout on tab close optional; mandatory refresh failure → login
- [ ] Rate-limit friendly retry UI
- [ ] No sensitive data in client-side error logs without redaction
- [ ] HTTPS in production (required for secure refresh cookie)

---

## 9. Out of scope for v1 frontend (match backend)

- Password reset
- Email verification UI
- Org switching / multi-org dashboard
- Billing, usage metering
- Secret versioning UI beyond optional `?version=` on reveal
- Mobile-native apps (responsive web is sufficient)
- Offline mode

---

## 10. References

| Resource | Location |
|----------|----------|
| Architecture | `ARCHITECTURE.md` |
| Single-org + invites ADR | `backend/docs/adr/0010-email-invitations-and-single-org-membership.md` |
| MFA + step-up ADR | `backend/docs/adr/0005-totp-mfa-and-step-up-authentication.md` |
| OpenAPI (local) | `http://localhost:8000/openapi.json` |
| Backend env template | `backend/.env.example` |
| Local stack | `backend/compose.yml` |

---

## 11. Handoff to implementation agent

Use this PRD plus generated OpenAPI types to produce:

1. **Screen inventory** with wireframes for each route in §3.5
2. **Component tree** and state flow for auth/session
3. **API hook/module map** (one function per endpoint group)
4. **Step-up and MFA modal** interaction specs
5. **Role/capability matrix** applied to each interactive element
6. **Test plan** covering §3.6 acceptance criteria against local Compose stack

The frontend should require **no backend changes** for core flows. Configuration is: API base URL, CORS-aligned origin, and `/accept-invite` route matching `INVITE_BASE_URL`.
