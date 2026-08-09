# ADR 0010: Email invitations and single-org membership

## Status

Accepted

## Context

VaultLog is a multi-tenant secrets manager where collaboration requires inviting
users into an organization. The product rule is **one user belongs to exactly one
organization**. Founding owners self-register and create an organization; all
other users join via email invitation.

## Decision

1. **Single-org constraint** — `UNIQUE(user_id)` on `membership` enforces one
   organization per user at the database level.

2. **Invitation model** — Tenant-owned `invitation` table with opaque tokens
   (SHA-256 hash stored), 7-day expiry, pending uniqueness per `(tenant_id, email)`.
   Roles limited to `admin`, `member`, `viewer`. Only owners may invite admins.

3. **Onboarding flows**
   - Owner: `POST /auth/register` → MFA enrollment required before tenant APIs.
   - Member: invitation email → `POST /invitations/accept` → normal login.

4. **Role-based org-wide vault access** — Members and viewers access all vaults
   in their organization by role (no per-vault grants required for onboarding).
   Owner/admin retain full administrative access.

5. **Email delivery** — `EmailSender` port with SMTP adapter (MailHog locally)
   and `LoggingEmailSender` for tests.

6. **Session AMR persistence** — `auth_session.amr` stores authentication methods
   so refresh tokens preserve MFA proof for step-up flows.

## Consequences

- No organization switching APIs; JWT `tid` is unambiguous per user.
- Public invitation preview/accept endpoints are rate-limited per IP.
- Member removal requires step-up MFA (`REMOVE_MEMBER` purpose).
- Grant APIs remain for owner/admin fine-grained management but are optional for
  standard member/viewer onboarding.
