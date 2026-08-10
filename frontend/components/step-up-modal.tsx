"use client";

import { useState } from "react";
import { isApiError } from "@/lib/api/errors";
import type { StepUpPurpose } from "@/lib/api/types";
import { useStepUpMutation } from "@/domains/auth/mutations";
import { Dialog } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

type StepUpModalProps = {
  purpose: StepUpPurpose;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void | Promise<void | unknown>;
};

export function StepUpModal({
  purpose,
  open,
  onClose,
  onSuccess,
}: StepUpModalProps) {
  const [code, setCode] = useState("");
  const stepUp = useStepUpMutation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await stepUp.mutateAsync({ code, purpose });
      setCode("");
      await onSuccess();
      onClose();
    } catch (error) {
      if (!isApiError(error)) return;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Confirm your identity"
      description="Enter the code from your authenticator app to continue with this action."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Authentication code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="6-digit code"
          autoComplete="one-time-code"
          inputMode="numeric"
          required
          minLength={6}
          maxLength={8}
        />
        {stepUp.isError && (
          <p className="text-sm text-danger" role="alert">
            {stepUp.error instanceof Error
              ? stepUp.error.message
              : "Verification failed. Try again."}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={stepUp.isPending}>
            Confirm
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
