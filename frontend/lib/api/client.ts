import { API_BASE_URL } from "@/lib/env";
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
import { notifySessionExpired } from "@/lib/auth/session-events";
import type { AccessTokenResponse } from "./types";

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

function requestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildFetchOptions(
  path: string,
  options: RequestOptions,
): RequestInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": requestId(),
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
  const response = await fetch(buildUrl(path), fetchOpts);

  if (
    response.status === 401 &&
    !options.skipAuth &&
    !options.skipRefresh &&
    path !== "/auth/refresh"
  ) {
    try {
      await refreshSession();
    } catch {
      expireSession();
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

function expireSession(): void {
  clearSession();
  notifySessionExpired();
}
