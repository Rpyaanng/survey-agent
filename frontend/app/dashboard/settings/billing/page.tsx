"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { PricingCards } from "@/components/pricing-cards";
import { PageHeader, UsageBar, notifyError } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { formatDate } from "@/lib/utils";
import type { Billing, Plan } from "@/lib/types";

const RANK = { free: 0, pro: 1, team: 2, enterprise: 3 };

function BillingView() {
  const params = useSearchParams();
  const { refresh } = useSession();
  const { data, mutate } = useSWR<Billing>("/billing");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const status = params.get("checkout");
    if (status === "success") toast.success("Subscription updated. Thanks for upgrading!");
    if (status === "cancelled") toast("Checkout cancelled. Your plan is unchanged.");
  }, [params]);

  async function afterDevChange(message: string) {
    await Promise.all([mutate(), refresh()]);
    toast.success(message);
  }

  async function checkout(plan: Plan) {
    setBusy(plan.id);
    try {
      const res = await api<{ url: string | null; dev_mode?: boolean }>("/billing/checkout", { method: "POST", body: { plan: plan.id } });
      if (res.url) window.location.href = res.url;
      else await afterDevChange(`Switched to ${plan.name} (development billing, no payment taken)`);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(null);
    }
  }

  async function portal() {
    setBusy("portal");
    try {
      const res = await api<{ url: string | null }>("/billing/portal", { method: "POST" });
      if (res.url) window.location.href = res.url;
      else await afterDevChange("Downgraded to Free (development billing)");
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(null);
    }
  }

  if (!data) return <Skeleton className="h-96 rounded-2xl" />;
  const { subscription, plan, usage } = data;
  const periodEnd = subscription.current_period_end;

  return (
    <div className="space-y-8">
      {!data.stripe_enabled && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-sm text-amber-200">
          Development billing mode: Stripe isn&apos;t configured, so plan changes apply instantly without payment.
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <section className="glass-panel rounded-2xl p-6">
          <div className="text-xs font-medium uppercase tracking-wider text-ink-faint">Current plan</div>
          <div className="mt-2 flex items-center gap-3">
            <h2 className="font-display text-3xl font-bold">{plan.name}</h2>
            <Badge tone={subscription.status === "active" ? "success" : subscription.status === "past_due" ? "warning" : "neutral"} className="capitalize">
              {subscription.status.replace("_", " ")}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-ink-muted">
            {plan.price_monthly ? `$${plan.price_monthly}/month` : plan.price_monthly === 0 ? "Free forever" : "Custom contract"}
            {periodEnd && ` · ${subscription.cancel_at_period_end ? "ends" : "renews"} ${formatDate(periodEnd)}`}
          </p>
          {subscription.status === "past_due" && (
            <p className="mt-3 text-sm text-amber-300">Your last payment failed. Update your payment method to keep access.</p>
          )}
          {data.can_manage && plan.id !== "free" && (
            <Button variant="secondary" className="mt-6" onClick={portal} loading={busy === "portal"}>
              {data.stripe_enabled ? (
                <>
                  <ExternalLink /> Manage billing & invoices
                </>
              ) : (
                "Downgrade to Free"
              )}
            </Button>
          )}
        </section>
        <section className="glass-panel rounded-2xl p-6">
          <div className="mb-5 flex items-baseline justify-between">
            <h2 className="font-display text-base font-semibold">Usage this period</h2>
            <span className="text-xs text-ink-faint">since {formatDate(usage.period_start)}</span>
          </div>
          <div className="space-y-5">
            <UsageBar label="Completed responses" {...usage.responses} />
            <UsageBar label="AI generations" {...usage.ai_generations} />
            <UsageBar label="Voice minutes" {...usage.voice_minutes} />
            <UsageBar label="Live surveys" {...usage.active_surveys} />
            <UsageBar label="Seats (incl. pending invites)" {...usage.seats} />
          </div>
        </section>
      </div>

      <section>
        <h2 className="mb-5 font-display text-lg font-semibold">Plans</h2>
        <PricingCards
          plans={data.plans}
          current={plan.id}
          action={(p) => {
            if (p.id === plan.id) return <Button variant="secondary" className="w-full" disabled>Current plan</Button>;
            if (p.id === "free") {
              return (
                <Button variant="secondary" className="w-full" disabled={!data.can_manage} loading={busy === "portal"} onClick={portal}>
                  Downgrade
                </Button>
              );
            }
            if (!p.purchasable) {
              return p.id === "enterprise" ? (
                <Button asChild variant="secondary" className="w-full">
                  <a href="mailto:sales@surveyagent.dev?subject=Enterprise%20plan">Contact sales</a>
                </Button>
              ) : null;
            }
            const upgrade = RANK[p.id] > RANK[plan.id];
            return (
              <Button
                className="w-full"
                variant={upgrade ? "default" : "secondary"}
                disabled={!data.can_manage}
                loading={busy === p.id}
                onClick={() => (upgrade || !subscription.managed_by_stripe ? checkout(p) : portal())}
              >
                {upgrade ? `Upgrade to ${p.name}` : `Switch to ${p.name}`}
              </Button>
            );
          }}
        />
        {!data.can_manage && <p className="mt-4 text-sm text-ink-faint">Only workspace owners and admins can change the plan.</p>}
      </section>
    </div>
  );
}

export default function BillingPage() {
  return (
    <>
      <PageHeader title="Billing" description="Your subscription, usage and invoices." />
      <Suspense>
        <BillingView />
      </Suspense>
    </>
  );
}
