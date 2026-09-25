import type { ReactNode } from "react";
import { Logo } from "./shared";

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle?: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-12">
      <div className="aurora pointer-events-none absolute inset-0 -z-10" aria-hidden />
      <div className="grid-fade pointer-events-none absolute inset-0 -z-10" aria-hidden />
      <Logo className="mb-10" />
      <div className="glass-panel w-full max-w-md rounded-2xl p-8 shadow-2xl">
        <h1 className="font-display text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-ink-muted">{subtitle}</p>}
        <div className="mt-7">{children}</div>
      </div>
      {footer && <div className="mt-6 text-sm text-ink-muted">{footer}</div>}
    </div>
  );
}
