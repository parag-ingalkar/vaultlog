type TokenState = {
  accessToken: string | null;
  expiresAt: number | null;
};

const state: TokenState = {
  accessToken: null,
  expiresAt: null,
};

export function getAccessToken(): string | null {
  if (!state.accessToken) return null;
  if (state.expiresAt && Date.now() >= state.expiresAt) {
    return state.accessToken;
  }
  return state.accessToken;
}

export function setAccessToken(accessToken: string, expiresIn: number): void {
  state.accessToken = accessToken;
  state.expiresAt = Date.now() + expiresIn * 1000;
}

export function getExpiresAt(): number | null {
  return state.expiresAt;
}

export function clearAccessToken(): void {
  state.accessToken = null;
  state.expiresAt = null;
}

export function hasAccessToken(): boolean {
  return state.accessToken !== null;
}
