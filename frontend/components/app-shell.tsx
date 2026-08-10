"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/domains/auth/auth-provider";

const navItems = [
  { href: "/vaults", label: "Vaults", show: () => true },
  {
    href: "/team",
    label: "Team",
    show: (caps?: { can_manage_members?: boolean; can_manage_invitations?: boolean }) =>
      caps?.can_manage_members || caps?.can_manage_invitations,
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
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              VaultLog
            </p>
            <p className="font-semibold">{me?.organization.name}</p>
          </div>
          <nav className="flex items-center gap-1">
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
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                      active
                        ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                        : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
