import {
  ApiError,
  StepUpRequiredError,
  isStepUpRequiredError,
} from "@/lib/api/errors";
import type { StepUpPurpose } from "@/lib/api/types";
import { getStepUpToken, clearStepUpToken } from "./step-up-cache";

export async function withStepUp<T>(
  purpose: StepUpPurpose,
  fn: (stepUpToken: string) => Promise<T>,
): Promise<T> {
  const token = getStepUpToken(purpose);
  if (!token) {
    throw new StepUpRequiredError(purpose);
  }

  try {
    return await fn(token);
  } catch (error) {
    if (error instanceof ApiError && error.isStepUpRequired()) {
      clearStepUpToken(purpose);
      throw new StepUpRequiredError(purpose);
    }
    throw error;
  }
}

export function ensureStepUpOrThrow(purpose: StepUpPurpose): string {
  const token = getStepUpToken(purpose);
  if (!token) {
    throw new StepUpRequiredError(purpose);
  }
  return token;
}

export { isStepUpRequiredError };
