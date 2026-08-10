import { parseApiError } from "./errors";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/token-store";
import {
  registerRefreshFn,
  scheduleProactiveRefresh,
  stopRefreshScheduler,
} from "@/lib/auth/refresh-scheduler";
import type { AccessTokenResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const COOKIE_ROUTES = new Set([
  "/auth/login",
  "/auth/mfa/verify",
  "/auth/refresh",
  "/auth/logout",
]);

type RequestOptions = {
  method?: string;
  body?: unknown;
  stepUpToken?: string;
  skipAuth?: boolean;
  skipRefresh?: boolean;
  headers?: Record<string, string>;
};

let refreshPromise: Promise<void> | null = null;

function buildUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
}

function needsCredentials(path: string): boolean {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return COOKIE_ROUTES.has(normalized);
}

function buildFetchOptions(
  path: string,
  options: RequestOptions,
): RequestInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (!options.skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  if (options.stepUpToken) {
    headers["X-Step-Up-Token"] = options.stepUpToken;
  }

  return {
    method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    credentials: needsCredentials(path) ? "include" : "same-origin",
  };
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const response = await fetch(
        buildUrl("/auth/refresh"),
        buildFetchOptions("/auth/refresh", {
          method: "POST",
          skipAuth: true,
          skipRefresh: true,
        }),
      );
      const data = await parseResponse<AccessTokenResponse>(response);
      setAccessToken(data.access_token, data.expires_in);
      scheduleProactiveRefresh();
    })().finally(() => {
      refreshPromise = null;
    });
  }
  await refreshPromise;
}

registerRefreshFn(refreshSession);

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const fetchOpts = buildFetchOptions(path, options);
  // #region agent log
  if (path === '/auth/login' || path === '/auth/me' || path === '/auth/refresh') {
    fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'client.ts:apiRequest',message:'auth request start',data:{path,credentials:fetchOpts.credentials,hasAuth:!!(fetchOpts.headers as Record<string,string>)?.Authorization},timestamp:Date.now(),hypothesisId:'A'})}).catch(()=>{});
  }
  // #endregion
  const response = await fetch(buildUrl(path), fetchOpts);
  // #region agent log
  if (path === '/auth/login' || path === '/auth/me' || path === '/auth/refresh') {
    fetch('http://127.0.0.1:7651/ingest/5b33c6d3-514d-482d-adf9-f29f91cb685f',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'67e7e7'},body:JSON.stringify({sessionId:'67e7e7',location:'client.ts:apiRequest',message:'auth request response',data:{path,status:response.status,ok:response.ok},timestamp:Date.now(),hypothesisId:'A'})}).catch(()=>{});
  }
  // #endregion

  if (
    response.status === 401 &&
    !options.skipAuth &&
    !options.skipRefresh &&
    path !== "/auth/refresh"
  ) {
    try {
      await refreshSession();
    } catch {
      clearAccessToken();
      stopRefreshScheduler();
      throw await parseApiError(response);
    }

    const retryResponse = await fetch(
      buildUrl(path),
      buildFetchOptions(path, { ...options, skipRefresh: true }),
    );
    return parseResponse<T>(retryResponse);
  }

  return parseResponse<T>(response);
}

export function storeAccessTokenFromResponse(data: AccessTokenResponse): void {
  setAccessToken(data.access_token, data.expires_in);
  scheduleProactiveRefresh();
}

export function clearSession(): void {
  clearAccessToken();
  stopRefreshScheduler();
}
