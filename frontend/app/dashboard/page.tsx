"use client";

import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, ListChecks, Plus } from "lucide-react";
import { EmptyState, PageHeader, StatCard, UsageBar } from "@/components/shared";
import { SurveyRow } from "@/components/survey-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/lib/session";
import type { Billing, Page, Survey } from "@/lib/types";

export default function OverviewPage() {
  const { session, can } = useSession();
  const { data: surveys } = useSWR<Page<Survey>>("/surveys?per_page=5");
  const { data: billing } = useSWR<Billing>("/billing");
  const firstName = session?.user.name?.split(" ")[0];

  const totalResponses = surveys?.items.reduce((sum, s) => sum + (s.responses?.completed ?? 0), 0);

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={firstName ? `Welcome back, ${firstName}` : "Welcome back"}
        description="Here's what's happening across your surveys."
        actions={
          can("editor") && (
            <Button asChild>
              <Link href="/dashboard/surveys/new">
                <Plus /> New survey
              </Link>
            </Button>
          )
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Live surveys" value={billing ? billing.usage.active_surveys.used : "—"} />
        <StatCard
          label="Responses this period"
          value={billing ? billing.usage.responses.used.toLocaleString() : "—"}
          hint={billing?.usage.responses.limit ? `of ${billing.usage.responses.limit.toLocaleString()} included` : "Unlimited"}
        />
        <StatCard label="Recent survey responses" value={totalResponses?.toLocaleString() ?? "—"} hint="Across your 5 latest surveys" />
        <StatCard label="Plan" value={<span className="capitalize">{billing?.plan.name ?? "—"}</span>} hint={billing?.subscription.status} />
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_320px]">
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold">Recent surveys</h2>
            <Link href="/dashboard/surveys" className="flex items-center gap-1 text-sm text-cyan-400 hover:underline">
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {!surveys ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-[72px] rounded-xl" />
              ))}
            </div>
          ) : surveys.items.length === 0 ? (
            <EmptyState
              icon={<ListChecks />}
              title="Create your first survey"
              description="Start from scratch, describe it to AI, or import a Google Form or PDF."
              action={
                <Button asChild>
                  <Link href="/dashboard/surveys/new">
                    <Plus /> New survey
                  </Link>
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {surveys.items.map((s) => (
                <SurveyRow key={s.id} survey={s} />
              ))}
            </div>
          )}
        </section>

        <aside className="glass-panel h-fit rounded-xl p-5">
          <h2 className="font-display text-base font-semibold">Usage this period</h2>
          {billing ? (
            <div className="mt-5 space-y-5">
              <UsageBar label="Responses" {...billing.usage.responses} />
              <UsageBar label="AI generations" {...billing.usage.ai_generations} />
              <UsageBar label="Voice minutes" {...billing.usage.voice_minutes} />
              <UsageBar label="Seats" {...billing.usage.seats} />
              <Button asChild variant="secondary" className="w-full">
                <Link href="/dashboard/settings/billing">Manage plan</Link>
              </Button>
            </div>
          ) : (
            <Skeleton className="mt-5 h-48" />
          )}
        </aside>
      </div>
    </>
  );
}
