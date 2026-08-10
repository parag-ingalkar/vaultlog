import type { StepUpPurpose } from "@/lib/api/types";

type CachedStepUp = {
  token: string;
  expiresAt: number;
};

const cache = new Map<StepUpPurpose, CachedStepUp>();

export function getStepUpToken(purpose: StepUpPurpose): string | null {
  const entry = cache.get(purpose);
  if (!entry) return null;
  if (Date.now() >= entry.expiresAt) {
    cache.delete(purpose);
    return null;
  }
  return entry.token;
}

export function setStepUpToken(
  purpose: StepUpPurpose,
  token: string,
  expiresIn: number,
): void {
  cache.set(purpose, {
    token,
    expiresAt: Date.now() + expiresIn * 1000,
  });
}

export function clearStepUpToken(purpose: StepUpPurpose): void {
  cache.delete(purpose);
}

export function clearAllStepUpTokens(): void {
  cache.clear();
}
