import { clearAccessToken, getExpiresAt } from "./token-store";

type RefreshFn = () => Promise<void>;

let refreshTimer: ReturnType<typeof setTimeout> | null = null;
let refreshFn: RefreshFn | null = null;

const REFRESH_BUFFER_MS = 2 * 60 * 1000;

export function registerRefreshFn(fn: RefreshFn): void {
  refreshFn = fn;
}

export function scheduleProactiveRefresh(): void {
  clearRefreshTimer();
  const expiresAt = getExpiresAt();
  if (!expiresAt) return;

  const delay = expiresAt - Date.now() - REFRESH_BUFFER_MS;
  if (delay <= 0) {
    runRefresh();
    return;
  }

  refreshTimer = setTimeout(() => {
    runRefresh();
  }, delay);
}

export function clearRefreshTimer(): void {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

export function stopRefreshScheduler(): void {
  clearRefreshTimer();
}

async function runRefresh(): Promise<void> {
  if (!refreshFn) return;
  try {
    await refreshFn();
    scheduleProactiveRefresh();
  } catch {
    clearAccessToken();
  }
}
