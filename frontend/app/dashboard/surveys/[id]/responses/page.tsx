"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Bot, Download, Inbox, Trash2, User } from "lucide-react";
import { toast } from "sonner";
import { EmptyState, ResponseStatusBadge, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, getActiveOrgId } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useSurvey } from "@/lib/use-survey";
import { formatAnswer, formatDateTime, formatDuration, timeAgo } from "@/lib/utils";
import type { Page, Survey, SurveyResponse } from "@/lib/types";

const CHANNEL_LABEL: Record<string, string> = { form: "Form", chat: "AI chat", voice: "Voice", phone: "Phone", api: "API" };

async function downloadExport(surveyId: string, format: "csv" | "json") {
  const res = await fetch(`/api/v1/surveys/${surveyId}/export?format=${format}`, {
    credentials: "include",
    headers: { "X-Org-Id": getActiveOrgId() ?? "", "X-Requested-With": "fetch" },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body?.error?.message ?? "Export failed", res.status, body?.error?.code ?? "error", body?.error?.details);
  }
  const blob = await res.blob();
  const name = res.headers.get("content-disposition")?.match(/filename="(.+)"/)?.[1] ?? `responses.${format}`;
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function ResponseDetail({ responseId, survey, onClose, onDeleted }: { responseId: string; survey: Survey; onClose: () => void; onDeleted: () => void }) {
  const { can } = useSession();
  const { data } = useSWR<SurveyResponse>(`/responses/${responseId}`);
  const answers = new Map((data?.answers ?? []).map((a) => [a.question_id, a]));
  const duration = data?.completed_at ? Math.round((new Date(data.completed_at).getTime() - new Date(data.started_at).getTime()) / 1000) : null;

  async function remove() {
    if (!window.confirm("Delete this response permanently?")) return;
    try {
      await api(`/responses/${responseId}`, { method: "DELETE" });
      toast.success("Response deleted");
      onDeleted();
    } catch (err) {
      notifyError(err);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-ink">{data?.respondent.name || data?.respondent.email || "Anonymous respondent"}</DialogTitle>
        </DialogHeader>
        {!data ? (
          <Skeleton className="h-64" />
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-muted">
              <ResponseStatusBadge status={data.status} />
              <span>{CHANNEL_LABEL[data.channel]}</span>
              <span>Started {formatDateTime(data.started_at)}</span>
              {duration != null && <span>Took {formatDuration(duration)}</span>}
              {data.respondent.phone && <span className="font-mono">{data.respondent.phone}</span>}
            </div>
            {data.error && <p className="rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{data.error}</p>}
            <div className="space-y-3">
              {(survey.questions ?? []).map((q, i) => {
                const answer = answers.get(q.id!);
                return (
                  <div key={q.id} className="rounded-xl bg-white/[0.03] p-4">
                    <div className="text-xs text-ink-faint">
                      {i + 1}. {q.title}
                    </div>
                    <div className={answer ? "mt-1.5 text-sm text-ink" : "mt-1.5 text-sm italic text-ink-faint"}>
                      {answer ? formatAnswer(answer.value) : "No answer"}
                    </div>
                    {answer?.raw_text && formatAnswer(answer.value) !== answer.raw_text && (
                      <div className="mt-1.5 text-xs text-ink-muted">&ldquo;{answer.raw_text}&rdquo;</div>
                    )}
                  </div>
                );
              })}
              {(data.answers ?? [])
                .filter((a) => !(survey.questions ?? []).some((q) => q.id === a.question_id))
                .map((a) => (
                  <div key={a.question_id} className="rounded-xl border border-dashed border-white/10 p-4">
                    <div className="text-xs text-ink-faint">Archived question</div>
                    <div className="mt-1.5 text-sm text-ink">{formatAnswer(a.value)}</div>
                  </div>
                ))}
            </div>
            {!!data.transcript?.length && (
              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink">Transcript</h3>
                <div className="space-y-3">
                  {data.transcript.map((turn, i) => (
                    <div key={i} className="flex gap-3">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06]">
                        {turn.role === "agent" ? <Bot className="h-3.5 w-3.5 text-cyan-400" /> : <User className="h-3.5 w-3.5 text-ink-muted" />}
                      </span>
                      <p className="text-sm leading-relaxed text-ink-muted">{turn.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {can("editor") && (
              <div className="flex justify-end border-t border-white/[0.06] pt-4">
                <Button variant="ghost" size="sm" onClick={remove} className="text-red-300">
                  <Trash2 /> Delete response
                </Button>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ResponsesView() {
  const { id, survey } = useSurvey();
  const router = useRouter();
  const params = useSearchParams();
  const selected = params.get("response");
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState<string | null>(null);
  const query = new URLSearchParams({ page: String(page), per_page: "25" });
  if (status) query.set("status", status);
  if (channel) query.set("channel", channel);
  const { data, mutate } = useSWR<Page<SurveyResponse>>(`/surveys/${id}/responses?${query}`, { keepPreviousData: true, refreshInterval: 15000 });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  const select = (responseId: string | null) =>
    router.replace(responseId ? `?response=${responseId}` : `/dashboard/surveys/${id}/responses`, { scroll: false });

  async function doExport(format: "csv" | "json") {
    setExporting(format);
    try {
      await downloadExport(id, format);
    } catch (err) {
      notifyError(err);
    } finally {
      setExporting(null);
    }
  }

  return (
    <>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2">
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="w-40" aria-label="Filter by status">
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="in_progress">In progress</option>
            <option value="processing">Processing</option>
            <option value="abandoned">Abandoned</option>
            <option value="failed">Failed</option>
          </Select>
          <Select value={channel} onChange={(e) => { setChannel(e.target.value); setPage(1); }} className="w-36" aria-label="Filter by channel">
            <option value="">All channels</option>
            {Object.entries(CHANNEL_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => doExport("csv")} loading={exporting === "csv"}>
            <Download /> CSV
          </Button>
          <Button variant="secondary" size="sm" onClick={() => doExport("json")} loading={exporting === "json"}>
            <Download /> JSON
          </Button>
        </div>
      </div>

      {!data ? (
        <Skeleton className="h-80 rounded-xl" />
      ) : data.items.length === 0 ? (
        <EmptyState icon={<Inbox />} title="No responses yet" description="Share your survey link and responses will appear here in real time." />
      ) : (
        <div className="glass-panel overflow-hidden rounded-xl">
          <table className="w-full text-sm">
            <thead className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-ink-faint">
              <tr>
                <th className="px-5 py-3 font-medium">Respondent</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="hidden px-5 py-3 font-medium sm:table-cell">Channel</th>
                <th className="hidden px-5 py-3 font-medium md:table-cell">Answers</th>
                <th className="px-5 py-3 text-right font-medium">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {data.items.map((r) => (
                <tr key={r.id} onClick={() => select(r.id)} className="cursor-pointer transition-colors hover:bg-white/[0.03]">
                  <td className="px-5 py-3.5 text-ink">{r.respondent.name || r.respondent.email || r.respondent.phone || <span className="text-ink-faint">Anonymous</span>}</td>
                  <td className="px-5 py-3.5">
                    <ResponseStatusBadge status={r.status} />
                  </td>
                  <td className="hidden px-5 py-3.5 text-ink-muted sm:table-cell">{CHANNEL_LABEL[r.channel]}</td>
                  <td className="hidden px-5 py-3.5 tabular-nums text-ink-muted md:table-cell">
                    {r.answer_count} / {survey?.question_count ?? "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right text-xs text-ink-faint">{timeAgo(r.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pages > 1 && (
            <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-sm text-ink-muted">
              <span>{data.total.toLocaleString()} responses</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      {selected && survey && (
        <ResponseDetail
          responseId={selected}
          survey={survey}
          onClose={() => select(null)}
          onDeleted={() => {
            select(null);
            mutate();
          }}
        />
      )}
    </>
  );
}

export default function ResponsesPage() {
  return (
    <Suspense>
      <ResponsesView />
    </Suspense>
  );
}
