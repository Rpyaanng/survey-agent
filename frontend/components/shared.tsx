"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Check, Copy, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { ApiError, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ResponseStatus, SurveyStatus } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Label } from "./ui/label";

export function Logo({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5 font-display font-bold text-ink", className)}>
      <span className="relative flex h-8 w-8 items-center justify-center rounded-lg gradient-accent shadow-lg shadow-cyan-500/20">
        <svg viewBox="0 0 24 24" className="h-4.5 w-4.5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M4 6h10M4 12h16M4 18h7" strokeLinecap="round" />
          <circle cx="19" cy="6" r="2" fill="currentColor" stroke="none" />
        </svg>
      </span>
      <span className="text-lg tracking-tight">Survey Agent</span>
    </Link>
  );
}

/** Toast an API error; plan-limit errors get an upgrade action. */
export function notifyError(error: unknown) {
  if (error instanceof ApiError && error.isPlanLimit) {
    toast.error(error.message, {
      action: { label: "Upgrade", onClick: () => (window.location.href = "/dashboard/settings/billing") },
    });
    return;
  }
  toast.error(errorMessage(error));
}

const SURVEY_STATUS: Record<SurveyStatus, { label: string; tone: "neutral" | "success" | "warning" }> = {
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Live", tone: "success" },
  closed: { label: "Closed", tone: "warning" },
};

export function SurveyStatusBadge({ status }: { status: SurveyStatus }) {
  const s = SURVEY_STATUS[status];
  return (
    <Badge tone={s.tone}>
      {status === "published" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
      {s.label}
    </Badge>
  );
}

const RESPONSE_STATUS: Record<ResponseStatus, { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" }> = {
  in_progress: { label: "In progress", tone: "info" },
  processing: { label: "Processing", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  abandoned: { label: "Abandoned", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};

export function ResponseStatusBadge({ status }: { status: ResponseStatus }) {
  const s = RESPONSE_STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <div className="text-xs font-medium uppercase tracking-wider text-cyan-400">{eyebrow}</div>}
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass-panel flex flex-col items-center rounded-2xl px-6 py-14 text-center", className)}>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.05] text-cyan-400 [&_svg]:h-6 [&_svg]:w-6">
        {icon}
      </div>
      <h3 className="font-display text-lg font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor} className="text-sm font-medium text-ink">
        {label}
      </Label>
      {children}
      {error ? <p className="text-xs text-red-400">{error}</p> : hint ? <p className="text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

export function CopyButton({ value, label = "Copy", className }: { value: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      className={className}
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }}
    >
      {copied ? <Check className="text-emerald-400" /> : <Copy />}
      {copied ? "Copied" : label}
    </Button>
  );
}

export function UpgradeCallout({ feature, plan = "Pro", className }: { feature: string; plan?: string; className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-violet-400/20 bg-violet-500/[0.07] p-4 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-violet-300" />
        <p className="text-sm text-ink-muted">
          <span className="font-medium text-ink">{feature}</span> is available on the {plan} plan and above.
        </p>
      </div>
      <Button asChild size="sm" variant="secondary">
        <Link href="/dashboard/settings/billing">View plans</Link>
      </Button>
    </div>
  );
}

export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="glass-panel rounded-xl p-5">
      <div className="text-xs font-medium uppercase tracking-wider text-ink-faint">{label}</div>
      <div className="mt-2 font-display text-2xl font-bold text-ink tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-muted">{hint}</div>}
    </div>
  );
}

export function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const tone = pct >= 90 ? "bg-red-400" : pct >= 70 ? "bg-amber-400" : "gradient-accent";
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink-muted">{label}</span>
        <span className="tabular-nums text-ink">
          {used.toLocaleString()}
          <span className="text-ink-faint"> / {limit == null ? "Unlimited" : limit.toLocaleString()}</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={cn("h-full rounded-full transition-all", limit == null ? "w-full bg-white/10" : tone)} style={limit == null ? undefined : { width: `${pct}%` }} />
      </div>
    </div>
  );
}
