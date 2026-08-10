# Product

## Register

product

## Users

Security-conscious team leads, ops engineers, and developers who share credentials within a single organization. They work at a desk under normal office lighting, often switching between tools while handling sensitive values. They need confidence that secrets stay protected without the UI feeling like a compliance audit dashboard.

## Product Purpose

VaultLog is a multi-tenant secrets manager for teams. Each organization owns encrypted vaults containing secrets (API keys, tokens, credentials). The frontend is the daily workspace for listing vaults, sharing access, revealing values deliberately, and reviewing activity when needed.

Success looks like: users register, enroll MFA, create vaults, share secrets with teammates, and trust the product enough to return without friction.

## Brand Personality

Minimal. Trustworthy. Inviting.

Voice is calm and direct — security is assumed, not shouted. The product should feel like a well-run operations desk, not a fortress or a marketing site.

## Anti-references

- Dark "hacker terminal" aesthetics with green-on-black
- Purple-on-white generic SaaS gradients
- Alarmist audit UIs with constant red badges and warning strips
- Identical feature-card grids and uppercase section eyebrows on every screen
- Over-decorated glassmorphism and heavy drop shadows on every panel

## Design Principles

1. **Calm confidence** — security through clarity and deliberate actions, not visual alarm.
2. **Reveal is deliberate** — secret values are hidden by default; reveal, copy, and hide are explicit steps.
3. **Hierarchy over decoration** — typography and spacing carry structure; accent color marks primary actions only.
4. **Earned familiarity** — patterns should feel recognizable to users of Stripe, Linear, or 1Password, without copying them literally.
5. **One org workspace** — the shell reflects a single organization; no platform-style tenant switching.

## Accessibility & Inclusion

- WCAG AA contrast for body text and interactive elements
- Visible focus rings on all interactive controls
- Respect `prefers-reduced-motion` for animations and transitions
- Form errors announced visually and associated with fields via labels
