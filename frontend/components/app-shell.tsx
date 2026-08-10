"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock } from "lucide-react";
import { useAuth } from "@/domains/auth/auth-provider";
import { cn } from "@/lib/cn";

const navItems = [
  { href: "/vaults", label: "Vaults", show: () => true },
  {
    href: "/team",
    label: "Team",
    show: (caps?: {
      can_manage_members?: boolean;
      can_manage_invitations?: boolean;
    }) => caps?.can_manage_members || caps?.can_manage_invitations,
  },
  {
    href: "/audit",
    label: "Audit",
    show: (caps?: { can_read_audit?: boolean }) => caps?.can_read_audit,
  },
  { href: "/settings", label: "Settings", show: () => true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { me, capabilities } = useAuth();

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-[var(--z-sticky)] border-b border-border bg-surface/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/vaults" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] bg-primary text-primary-ink">
                <Lock className="h-4 w-4" aria-hidden />
              </span>
              <span className="text-base font-semibold text-ink">VaultLog</span>
            </Link>
            <span className="hidden h-4 w-px bg-border sm:block" aria-hidden />
            <p className="hidden truncate text-sm text-muted sm:block">
              {me?.organization.name}
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-1" aria-label="Main">
            {navItems
              .filter((item) => item.show(capabilities))
              .map((item) => {
                const active =
                  pathname === item.href ||
                  pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-[var(--radius-control)] px-3 py-2 text-sm font-medium transition-colors duration-[var(--transition)]",
                      active
                        ? "bg-primary-subtle text-primary"
                        : "text-muted hover:bg-surface-2 hover:text-ink",
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    {item.label}
                  </Link>
                );
              })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        {children}
      </main>
    </div>
  );
}
