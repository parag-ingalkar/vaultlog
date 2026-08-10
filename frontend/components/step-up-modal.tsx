"use client";

import { useState } from "react";
import { isApiError } from "@/lib/api/errors";
import type { StepUpPurpose } from "@/lib/api/types";
import { useStepUpMutation } from "@/domains/auth/mutations";
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

  if (!open) return null;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold">Confirm with authenticator</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Enter the code from your authenticator app to continue.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
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
            <p className="text-sm text-red-600">
              {stepUp.error instanceof Error
                ? stepUp.error.message
                : "Verification failed"}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={stepUp.isPending}>
              {stepUp.isPending ? "Verifying…" : "Confirm"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
