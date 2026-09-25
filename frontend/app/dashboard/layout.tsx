"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  BarChart3,
  Check,
  ChevronsUpDown,
  CreditCard,
  Code2,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Plus,
  Settings,
  Users,
  X,
} from "lucide-react";
import { Logo } from "@/components/shared";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { SessionProvider, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { Organization } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/surveys", label: "Surveys", icon: ListChecks },
  { href: "/dashboard/settings/team", label: "Team", icon: Users },
  { href: "/dashboard/settings/billing", label: "Billing", icon: CreditCard },
  { href: "/dashboard/settings/developers", label: "Developers", icon: Code2 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings, exact: true },
];

function OrgSwitcher() {
  const { session, org, switchOrg, refresh } = useSession();
  if (!org || !session) return <Skeleton className="h-12 w-full rounded-lg" />;

  async function createOrg() {
    const name = window.prompt("Name your new workspace");
    if (!name?.trim()) return;
    const created = await api<Organization>("/orgs", { method: "POST", body: { name: name.trim() } });
    await refresh();
    switchOrg(created.id);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-cyan-500/30 to-violet-500/30 font-display text-sm font-bold text-ink">
          {org.name.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">{org.name}</span>
          <span className="block text-xs capitalize text-ink-faint">{org.plan} plan</span>
        </span>
        <ChevronsUpDown className="h-4 w-4 text-ink-faint" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60 border-white/10 bg-popover" align="start">
        <DropdownMenuLabel className="text-xs text-ink-faint">Workspaces</DropdownMenuLabel>
        {session.organizations.map((o) => (
          <DropdownMenuItem key={o.id} onClick={() => o.id !== org.id && switchOrg(o.id)} className="gap-2">
            <span className="flex-1 truncate">{o.name}</span>
            {o.id === org.id && <Check className="h-4 w-4 text-cyan-400" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={createOrg} className="gap-2">
          <Plus className="h-4 w-4" /> New workspace
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="space-y-1">
      {NAV.map(({ href, label, icon: Icon, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-white/[0.07] text-ink" : "text-ink-muted hover:bg-white/[0.04] hover:text-ink",
            )}
          >
            <Icon className={cn("h-4 w-4", active ? "text-cyan-400" : "text-ink-faint")} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserMenu() {
  const { session, logout } = useSession();
  if (!session) return null;
  const initials = (session.user.name || session.user.email).slice(0, 2).toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white/[0.04]">
        <span className="flex h-8 w-8 items-center justify-center rounded-full gradient-accent text-xs font-bold text-white">{initials}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">{session.user.name}</span>
          <span className="block truncate text-xs text-ink-faint">{session.user.email}</span>
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56 border-white/10 bg-popover" align="end" side="top">
        <DropdownMenuItem asChild>
          <Link href="/dashboard/settings">Account settings</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className="gap-2 text-red-300">
          <LogOut className="h-4 w-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { org } = useSession();

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center justify-between px-1 pt-1">
        <Logo href="/dashboard" />
        <button className="lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close menu">
          <X className="h-5 w-5 text-ink-muted" />
        </button>
      </div>
      <OrgSwitcher />
      <SidebarNav onNavigate={() => setMobileOpen(false)} />
      <div className="mt-auto space-y-3">
        {org?.plan === "free" && (
          <Link
            href="/dashboard/settings/billing"
            className="block rounded-xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/10 to-violet-500/10 p-4"
          >
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <BarChart3 className="h-4 w-4 text-cyan-400" /> Upgrade to Pro
            </div>
            <p className="mt-1 text-xs text-ink-muted">Voice interviews, imports, AI insights and exports.</p>
          </Link>
        )}
        <UserMenu />
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-white/[0.06] bg-ground-raised/60 lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-white/10 bg-ground-raised">{sidebar}</aside>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/[0.06] bg-ground/80 px-4 py-3 backdrop-blur lg:hidden">
          <Logo href="/dashboard" />
          <button onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5 text-ink" />
          </button>
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
          {org ? children : <Skeleton className="h-40 w-full rounded-xl" />}
        </main>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <Shell>{children}</Shell>
    </SessionProvider>
  );
}
