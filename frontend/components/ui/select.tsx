import type { SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { Label } from "./label";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string;
};

export function Select({
  label,
  error,
  className = "",
  id,
  children,
  ...props
}: SelectProps) {
  const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className="space-y-1.5">
      {label && <Label htmlFor={selectId}>{label}</Label>}
      <select
        id={selectId}
        aria-invalid={error ? true : undefined}
        className={cn(
          "w-full rounded-[var(--radius-control)] border border-border bg-surface px-3 py-2 text-sm text-ink transition-[border-color,box-shadow] duration-[var(--transition)] focus:border-primary focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-50",
          error && "border-danger",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      {error && (
        <p className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
