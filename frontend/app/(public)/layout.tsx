import type { ReactNode } from "react";
import Link from "next/link";
import { Lock } from "lucide-react";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-2">
      <header className="px-4 py-6 sm:px-6">
        <Link href="/login" className="inline-flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] bg-primary text-primary-ink">
            <Lock className="h-4 w-4" aria-hidden />
          </span>
          <span className="text-base font-semibold text-ink">VaultLog</span>
        </Link>
      </header>

      <div className="flex flex-1 items-center justify-center px-4 pb-12">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}
