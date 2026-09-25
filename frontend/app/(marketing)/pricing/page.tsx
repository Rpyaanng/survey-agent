"use client";

import Link from "next/link";
import useSWR from "swr";
import { Check, Minus } from "lucide-react";
import { PricingCards } from "@/components/pricing-cards";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Plan } from "@/lib/types";

const FEATURE_ROWS: { key: string; label: string }[] = [
  { key: "chat", label: "AI chat interviews" },
  { key: "ai_builder", label: "AI survey builder" },
  { key: "import", label: "Google Forms & PDF import" },
  { key: "voice", label: "Browser voice interviews" },
  { key: "export", label: "CSV / JSON export" },
  { key: "insights", label: "AI insights" },
  { key: "remove_branding", label: "Remove Survey Agent branding" },
  { key: "phone", label: "Outbound phone interviews" },
  { key: "api_access", label: "REST API" },
  { key: "webhooks", label: "Webhooks" },
];

const LIMIT_ROWS: { key: string; label: string }[] = [
  { key: "active_surveys", label: "Live surveys" },
  { key: "responses_per_month", label: "Responses / month" },
  { key: "voice_minutes_per_month", label: "Voice minutes / month" },
  { key: "ai_generations_per_month", label: "AI generations / month" },
  { key: "seats", label: "Seats" },
];

const fmt = (v: number | null | undefined) => (v == null ? "Unlimited" : v === 0 ? "—" : v.toLocaleString());

export default function PricingPage() {
  const { data } = useSWR<{ plans: Plan[] }>("/public/plans");

  return (
    <div className="relative px-4 pb-24 pt-32 sm:px-6 sm:pt-40 lg:px-8">
      <div className="aurora absolute inset-0 -z-10" aria-hidden />
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Simple, <span className="text-gradient-accent">usage-based</span> plans
          </h1>
          <p className="mt-4 text-lg text-ink-muted">Start free. Upgrade as your research program grows. Cancel anytime.</p>
        </div>

        <div className="mt-16">
          {!data ? (
            <div className="grid gap-4 md:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-96 rounded-2xl" />
              ))}
            </div>
          ) : (
            <PricingCards
              plans={data.plans}
              action={(plan) =>
                plan.id === "enterprise" ? (
                  <Button asChild variant="secondary" className="w-full">
                    <a href="mailto:sales@surveyagent.dev?subject=Enterprise%20plan">Contact sales</a>
                  </Button>
                ) : (
                  <Button asChild className="w-full" variant={plan.id === "pro" ? "default" : "secondary"}>
                    <Link href="/signup">{plan.id === "free" ? "Start free" : `Start with ${plan.name}`}</Link>
                  </Button>
                )
              }
            />
          )}
        </div>

        {data && (
          <div className="glass-panel mt-16 overflow-x-auto rounded-2xl">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-6 py-4 text-left font-medium text-ink-faint">Compare plans</th>
                  {data.plans.map((p) => (
                    <th key={p.id} className="px-6 py-4 text-center font-display font-semibold text-ink">
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {LIMIT_ROWS.map((row) => (
                  <tr key={row.key}>
                    <td className="px-6 py-3 text-ink-muted">{row.label}</td>
                    {data.plans.map((p) => (
                      <td key={p.id} className="px-6 py-3 text-center tabular-nums text-ink">
                        {fmt(p.limits[row.key])}
                      </td>
                    ))}
                  </tr>
                ))}
                {FEATURE_ROWS.map((row) => (
                  <tr key={row.key}>
                    <td className="px-6 py-3 text-ink-muted">{row.label}</td>
                    {data.plans.map((p) => (
                      <td key={p.id} className="px-6 py-3 text-center">
                        {p.features.includes(row.key) ? (
                          <Check className="mx-auto h-4 w-4 text-cyan-400" aria-label="Included" />
                        ) : (
                          <Minus className="mx-auto h-4 w-4 text-ink-faint" aria-label="Not included" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
