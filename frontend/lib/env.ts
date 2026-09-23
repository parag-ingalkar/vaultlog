/**
 * Public env is inlined at build time. Always read NEXT_PUBLIC_* via
 * static property access so Next.js can replace the value.
 */
function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function readApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (fromEnv) {
    return trimTrailingSlash(fromEnv);
  }
  if (process.env.NODE_ENV !== "production") {
    return "/api/v1";
  }
  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL must be set for production builds. Use /api/v1 with API_PROXY_TARGET, or an absolute FastAPI origin listed in CORS_ORIGINS.",
  );
}

export const API_BASE_URL = readApiBaseUrl();
