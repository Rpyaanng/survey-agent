import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Plan } from "@/lib/types";

export function PricingCards({ plans, action, current }: { plans: Plan[]; action: (plan: Plan) => ReactNode; current?: string }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {plans.map((plan) => {
        const featured = plan.id === "pro";
        return (
          <div
            key={plan.id}
            className={cn(
              "glass-panel relative flex flex-col rounded-2xl p-6",
              featured && "ring-glow border-cyan-400/40",
              current === plan.id && "border-emerald-400/40",
            )}
          >
            {featured && (
              <span className="gradient-accent absolute -top-3 left-6 rounded-full px-3 py-0.5 text-xs font-semibold text-white">Most popular</span>
            )}
            <div className="flex items-center justify-between">
              <h3 className="font-display text-lg font-semibold">{plan.name}</h3>
              {current === plan.id && <span className="text-xs font-medium text-emerald-300">Current plan</span>}
            </div>
            <p className="mt-1 min-h-10 text-sm text-ink-muted">{plan.tagline}</p>
            <div className="mt-5 flex items-baseline gap-1">
              {plan.price_monthly == null ? (
                <span className="font-display text-3xl font-bold text-ink">Custom</span>
              ) : (
                <>
                  <span className="font-display text-4xl font-bold text-ink">${plan.price_monthly}</span>
                  <span className="text-sm text-ink-faint">/ month</span>
                </>
              )}
            </div>
            <ul className="mt-6 flex-1 space-y-2.5">
              {plan.highlights.map((h) => (
                <li key={h} className="flex gap-2.5 text-sm text-ink-muted">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
                  {h}
                </li>
              ))}
            </ul>
            <div className="mt-6">{action(plan)}</div>
          </div>
        );
      })}
    </div>
  );
}
