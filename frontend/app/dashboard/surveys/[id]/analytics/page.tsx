"use client";

import { useState } from "react";
import useSWR from "swr";
import { BarChart3, Lightbulb, Quote, Sparkles } from "lucide-react";
import { BarList, ColumnChart, NpsBreakdown, Timeline } from "@/components/charts";
import { EmptyState, StatCard, UpgradeCallout, notifyError } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { TYPE_META } from "@/lib/questions";
import { useSession } from "@/lib/session";
import { useSurveyId } from "@/lib/use-survey";
import { formatDuration } from "@/lib/utils";
import type { Analytics, Insights, QuestionStats } from "@/lib/types";

const CHANNEL_LABEL: Record<string, string> = { form: "Web form", chat: "AI chat", voice: "Browser voice", phone: "Phone", api: "API" };
const SENTIMENT_TONE = { positive: "success", neutral: "neutral", negative: "danger", mixed: "warning" } as const;

function QuestionCard({ stats, index }: { stats: QuestionStats; index: number }) {
  const Icon = TYPE_META[stats.type].icon;
  return (
    <div className="glass-panel rounded-xl p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-ink-faint">
            <Icon className="h-3.5 w-3.5" /> Q{index + 1} · {TYPE_META[stats.type].label}
          </div>
          <h3 className="mt-1 font-medium leading-snug text-ink">{stats.title}</h3>
        </div>
        <div className="shrink-0 text-right text-xs text-ink-faint">
          <div className="tabular-nums text-ink">{stats.answered.toLocaleString()} answered</div>
          {stats.skipped > 0 && <div className="tabular-nums">{stats.skipped.toLocaleString()} skipped</div>}
        </div>
      </div>
      <div className="mt-5">
        {stats.answered === 0 ? (
          <p className="text-sm text-ink-faint">No answers yet.</p>
        ) : stats.nps ? (
          <div className="space-y-6">
            <NpsBreakdown nps={stats.nps} />
            {stats.distribution && <ColumnChart items={stats.distribution} height={110} />}
          </div>
        ) : stats.type === "rating" && stats.distribution ? (
          <div>
            <div className="mb-4 flex items-baseline gap-2">
              <span className="text-3xl font-semibold text-ink">{stats.average?.toFixed(1)}</span>
              <span className="text-sm text-ink-muted">average</span>
            </div>
            <ColumnChart items={stats.distribution} />
          </div>
        ) : stats.distribution ? (
          <>
            <BarList items={stats.distribution} total={stats.type === "multiple_choice" ? stats.answered : stats.distribution.reduce((s, d) => s + d.count, 0)} />
            {stats.note && <p className="mt-3 text-xs text-ink-faint">{stats.note}; percentages are of respondents.</p>}
          </>
        ) : stats.average != null ? (
          <dl className="grid grid-cols-4 gap-3 text-center">
            {[
              ["Average", stats.average],
              ["Median", stats.median],
              ["Min", stats.min],
              ["Max", stats.max],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-lg bg-white/[0.03] py-3">
                <dt className="text-xs text-ink-faint">{label}</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto pr-1">
            {(stats.samples ?? []).map((sample, i) => (
              <li key={i} className="rounded-lg bg-white/[0.03] px-3.5 py-2.5 text-sm leading-relaxed text-ink-muted">
                {sample}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function InsightsPanel({ surveyId, completed }: { surveyId: string; completed: number }) {
  const { org, can } = useSession();
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);

  if (org?.plan === "free") return <UpgradeCallout feature="AI insights" />;

  async function generate() {
    setLoading(true);
    try {
      setInsights(await api<Insights>(`/surveys/${surveyId}/insights`, { method: "POST" }));
    } catch (err) {
      notifyError(err);
    } finally {
      setLoading(false);
    }
  }

  if (!insights) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-xl border border-violet-400/20 bg-gradient-to-br from-violet-500/[0.08] to-cyan-500/[0.05] p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 h-5 w-5 text-violet-300" />
          <div>
            <div className="font-medium text-ink">AI insights</div>
            <p className="mt-0.5 text-sm text-ink-muted">Key findings, themes from open-ended answers, and recommended next steps.</p>
          </div>
        </div>
        {can("editor") && (
          <Button onClick={generate} loading={loading} disabled={completed === 0}>
            <Sparkles /> Generate insights
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="glass-panel space-y-6 rounded-xl p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-violet-300">
            <Sparkles className="h-3.5 w-3.5" /> AI insights
          </div>
          <h2 className="mt-2 font-display text-xl font-semibold">{insights.headline}</h2>
        </div>
        <Badge tone={SENTIMENT_TONE[insights.sentiment]} className="capitalize">
          {insights.sentiment}
        </Badge>
      </div>
      <p className="leading-relaxed text-ink-muted">{insights.summary}</p>
      {insights.key_findings.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {insights.key_findings.map((f) => (
            <div key={f.title} className="rounded-lg bg-white/[0.03] p-4">
              <div className="font-medium text-ink">{f.title}</div>
              <p className="mt-1 text-sm text-ink-muted">{f.detail}</p>
            </div>
          ))}
        </div>
      )}
      {insights.themes.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink">Themes</h3>
          <div className="space-y-3">
            {insights.themes.map((t) => (
              <div key={t.theme} className="flex gap-3">
                <Quote className="mt-1 h-4 w-4 shrink-0 text-ink-faint" />
                <div>
                  <div className="text-sm text-ink">
                    {t.theme} <span className="text-ink-faint">· {t.prevalence}</span>
                  </div>
                  {t.quote && <p className="mt-0.5 text-sm italic text-ink-muted">&ldquo;{t.quote}&rdquo;</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {insights.recommendations.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink">Recommendations</h3>
          <ul className="space-y-2">
            {insights.recommendations.map((r) => (
              <li key={r} className="flex gap-2.5 text-sm text-ink-muted">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" /> {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const id = useSurveyId();
  const { data } = useSWR<Analytics>(`/surveys/${id}/analytics`, { refreshInterval: 30000 });

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  const { summary } = data;
  if (summary.started === 0) {
    return <EmptyState icon={<BarChart3 />} title="No data yet" description="Analytics appear as soon as the first responses come in." />;
  }
  const channelTotal = data.channels.reduce((s, c) => s + c.count, 0);

  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Completed" value={summary.completed.toLocaleString()} hint={`${summary.started.toLocaleString()} started`} />
        <StatCard label="Completion rate" value={summary.completion_rate == null ? "—" : `${Math.round(summary.completion_rate * 100)}%`} />
        <StatCard label="Median time" value={formatDuration(summary.median_duration_seconds)} />
        <StatCard label="In progress" value={summary.in_progress.toLocaleString()} />
      </div>

      <InsightsPanel surveyId={id} completed={summary.completed} />

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <section className="glass-panel rounded-xl p-5">
          <h2 className="font-display text-base font-semibold">Completed responses per day</h2>
          <p className="mb-4 text-xs text-ink-faint">Last 30 days</p>
          <Timeline points={data.timeline} />
        </section>
        <section className="glass-panel rounded-xl p-5">
          <h2 className="mb-4 font-display text-base font-semibold">Responses by channel</h2>
          {data.channels.length ? (
            <BarList items={data.channels.map((c) => ({ label: CHANNEL_LABEL[c.channel] ?? c.channel, count: c.count }))} total={channelTotal} />
          ) : (
            <p className="text-sm text-ink-faint">No completed responses yet.</p>
          )}
        </section>
      </div>

      <section>
        <h2 className="mb-4 font-display text-lg font-semibold">Question breakdown</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.questions.map((q, i) => (
            <QuestionCard key={q.question_id} stats={q} index={i} />
          ))}
        </div>
      </section>
    </div>
  );
}
