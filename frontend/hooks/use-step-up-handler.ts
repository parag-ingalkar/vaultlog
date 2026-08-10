import { isStepUpRequiredError } from "@/lib/auth/with-step-up";
import type { StepUpPurpose } from "@/lib/api/types";
import { useState } from "react";

type StepUpState = {
  purpose: StepUpPurpose;
  retry: () => Promise<unknown>;
};

export function useStepUpHandler() {
  const [stepUpState, setStepUpState] = useState<StepUpState | null>(null);

  const handleStepUpError = (
    error: unknown,
    purpose: StepUpPurpose,
    retry: () => Promise<unknown>,
  ): boolean => {
    if (isStepUpRequiredError(error)) {
      setStepUpState({ purpose, retry });
      return true;
    }
    return false;
  };

  const clearStepUp = () => setStepUpState(null);

  return { stepUpState, clearStepUp, handleStepUpError };
}
