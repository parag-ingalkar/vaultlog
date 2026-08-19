# VaultLog frontend

Next.js client for the VaultLog FastAPI backend. It talks only to `/api/v1` using generated OpenAPI types and TanStack Query.

## Local development

1. Start the FastAPI stack (`backend/compose.yml`).
2. Copy environment defaults:

```bash
cp .env.example .env.local
```

3. Install and run:

```bash
pnpm install
pnpm dev
```

The app is at [http://localhost:3000](http://localhost:3000). By default the browser calls `/api/v1`, and Next.js proxies that prefix to `API_PROXY_TARGET` (`http://localhost:8000`). Keep `CORS_ORIGINS=http://localhost:3000` and `INVITE_BASE_URL=http://localhost:3000/accept-invite` in the backend env.

## Environment variables

| Variable | Scope | Purpose |
|----------|--------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Build (inlined) | API prefix used by the browser. Prefer `/api/v1`. An absolute origin (for example `https://api.example.com/api/v1`) is allowed if it is listed in backend `CORS_ORIGINS`. |
| `API_PROXY_TARGET` | Server | FastAPI origin for Next.js rewrites of `/api/v1/*`. Required when the public API URL is relative. |

`NEXT_PUBLIC_*` values are baked in at `next build`. Changing the API host at container runtime only works if you built with a relative `/api/v1` prefix and set `API_PROXY_TARGET` for the running Next.js process.

Production build fails if `NEXT_PUBLIC_API_BASE_URL` is unset.

## Production notes

- Serve the app over HTTPS and set backend `REFRESH_COOKIE_SECURE=true`.
- Same-origin `/api/v1` (reverse proxy or `API_PROXY_TARGET`) keeps the HttpOnly refresh cookie first-party.
- Access tokens stay in memory only; refresh tokens never enter JavaScript.
- Secret plaintext is never written to `localStorage` / `sessionStorage` and is dropped when leaving the secret page.
- Generate API types from the backend contract with `pnpm generate:api` (also runs before `pnpm build`).

## Scripts

```bash
pnpm dev          # development server
pnpm lint         # ESLint (includes TanStack Query rules)
pnpm build        # generate OpenAPI types + production build
pnpm start        # serve the production build
```
