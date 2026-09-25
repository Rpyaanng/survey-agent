"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { AudioLines, CheckCircle2, ClipboardList, Lock, MessageSquareText } from "lucide-react";
import { ChatMode } from "@/components/respondent/chat-mode";
import { FormMode } from "@/components/respondent/form-mode";
import { VoiceMode } from "@/components/respondent/voice-mode";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Mode, PublicSurvey } from "@/lib/types";

const MODE_META: Record<Mode, { label: string; description: string; icon: typeof ClipboardList }> = {
  chat: { label: "Chat", description: "Answer in a quick conversation", icon: MessageSquareText },
  voice: { label: "Talk", description: "Speak your answers out loud", icon: AudioLines },
  form: { label: "Form", description: "Fill out a classic form", icon: ClipboardList },
};

const GRID_COLS: Record<number, string> = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" };

interface Started {
  mode: Mode;
  responseId?: string;
  responseToken?: string;
}

function Shell({ survey, embed, children }: { survey?: PublicSurvey; embed: boolean; children: React.ReactNode }) {
  const brand = survey?.organization.branding.primary_color;
  return (
    <div className="relative min-h-dvh" style={brand ? ({ "--brand": brand } as React.CSSProperties) : undefined}>
      {!embed && <div className="aurora pointer-events-none fixed inset-0 -z-10" aria-hidden />}
      <div className={cn("mx-auto w-full max-w-2xl px-4", embed ? "py-4" : "py-10 sm:py-16")}>
        {survey && !embed && (
          <div className="mb-8 flex items-center gap-3">
            {survey.organization.branding.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={survey.organization.branding.logo_url} alt={survey.organization.name} className="h-8 max-w-32 object-contain" />
            ) : (
              <span className="brand-bg flex h-8 w-8 items-center justify-center rounded-lg font-display text-sm font-bold text-white">
                {survey.organization.name.slice(0, 1)}
              </span>
            )}
            <span className="text-sm font-medium text-ink-muted">{survey.organization.name}</span>
          </div>
        )}
        {children}
        {survey?.show_branding && (
          <a href="/" target="_blank" className="mt-10 block text-center text-xs text-ink-faint hover:text-ink-muted">
            Powered by <span className="font-semibold">Survey Agent</span>
          </a>
        )}
      </div>
    </div>
  );
}

function SurveyExperience() {
  const { token } = useParams<{ token: string }>();
  const params = useSearchParams();
  const embed = params.get("embed") === "1";
  const storageKey = `sa_response_${token}`;
  const { data: survey, error } = useSWR<PublicSurvey>(`/public/surveys/${token}`, { shouldRetryOnError: false });
  const [started, setStarted] = useState<Started | null>(null);
  const [done, setDone] = useState(false);
  const [respondent, setRespondent] = useState<Record<string, string>>({});
  const [starting, setStarting] = useState<Mode | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  // Resume an in-progress form/chat response after a refresh.
  useEffect(() => {
    const saved = sessionStorage.getItem(storageKey);
    if (saved) setStarted(JSON.parse(saved));
  }, [storageKey]);

  const finish = useCallback(() => {
    sessionStorage.removeItem(storageKey);
    setDone(true);
  }, [storageKey]);

  const needsDetails = !!(survey?.collect.name || survey?.collect.email);
  const detailsValid = (!survey?.collect.name || respondent.name?.trim()) && (!survey?.collect.email || /\S+@\S+\.\S+/.test(respondent.email ?? ""));

  async function begin(mode: Mode) {
    if (!detailsValid) return;
    if (mode === "voice") return setStarted({ mode });
    setStarting(mode);
    setStartError(null);
    try {
      const res = await api<{ response_id: string; response_token: string }>(`/public/surveys/${token}/responses`, {
        method: "POST",
        body: { channel: mode, respondent },
      });
      const next = { mode, responseId: res.response_id, responseToken: res.response_token };
      sessionStorage.setItem(storageKey, JSON.stringify(next));
      setStarted(next);
    } catch (err) {
      setStartError(errorMessage(err));
    } finally {
      setStarting(null);
    }
  }

  // ?mode=chat deep links skip the picker when no details are needed.
  const preferred = params.get("mode") as Mode | null;
  useEffect(() => {
    if (survey?.accepting_responses && preferred && survey.modes.includes(preferred) && !needsDetails && !started && !starting) {
      begin(preferred);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [survey]);

  if (error) {
    return (
      <Shell embed={embed}>
        <div className="glass-panel rounded-2xl p-10 text-center">
          <h1 className="font-display text-2xl font-bold">Survey not found</h1>
          <p className="mt-2 text-ink-muted">This link may be mistyped or the survey was removed.</p>
        </div>
      </Shell>
    );
  }
  if (!survey) {
    return (
      <Shell embed={embed}>
        <Skeleton className="h-80 rounded-2xl" />
      </Shell>
    );
  }

  if (done) {
    return (
      <Shell survey={survey} embed={embed}>
        <div className="glass-panel rounded-2xl px-8 py-14 text-center">
          <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-400" />
          <h1 className="mt-5 font-display text-2xl font-bold">Thank you!</h1>
          <p className="mx-auto mt-2 max-w-md text-ink-muted">{survey.closing_message || "Your response has been recorded."}</p>
        </div>
      </Shell>
    );
  }

  if (!survey.accepting_responses) {
    return (
      <Shell survey={survey} embed={embed}>
        <div className="glass-panel rounded-2xl px-8 py-14 text-center">
          <Lock className="mx-auto h-10 w-10 text-ink-faint" />
          <h1 className="mt-5 font-display text-2xl font-bold">{survey.title}</h1>
          <p className="mt-2 text-ink-muted">This survey is no longer accepting responses.</p>
        </div>
      </Shell>
    );
  }

  if (started?.mode === "voice") {
    return (
      <Shell survey={survey} embed={embed}>
        <VoiceMode survey={survey} respondent={respondent} onDone={finish} />
      </Shell>
    );
  }
  if (started?.responseId && started.responseToken) {
    const Mode = started.mode === "chat" ? ChatMode : FormMode;
    return (
      <Shell survey={survey} embed={embed}>
        {started.mode === "form" && (
          <div className="mb-6">
            <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">{survey.title}</h1>
            {survey.description && <p className="mt-2 text-ink-muted">{survey.description}</p>}
          </div>
        )}
        <Mode survey={survey} responseId={started.responseId} responseToken={started.responseToken} onDone={finish} />
      </Shell>
    );
  }

  const modes = (["chat", "voice", "form"] as Mode[]).filter((m) => survey.modes.includes(m));
  return (
    <Shell survey={survey} embed={embed}>
      <div className="glass-panel rounded-2xl p-6 sm:p-10">
        <h1 className="font-display text-3xl font-bold tracking-tight">{survey.title}</h1>
        {survey.description && <p className="mt-3 leading-relaxed text-ink-muted">{survey.description}</p>}
        {survey.welcome_message && <p className="mt-3 leading-relaxed text-ink-muted">{survey.welcome_message}</p>}
        <p className="mt-4 text-xs text-ink-faint">
          {survey.questions.length} questions · about {Math.max(1, Math.round(survey.questions.length * 0.4))} min
        </p>

        {needsDetails && (
          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            {survey.collect.name && (
              <Input placeholder="Your name" value={respondent.name ?? ""} onChange={(e) => setRespondent({ ...respondent, name: e.target.value })} aria-label="Your name" />
            )}
            {survey.collect.email && (
              <Input type="email" placeholder="Your email" value={respondent.email ?? ""} onChange={(e) => setRespondent({ ...respondent, email: e.target.value })} aria-label="Your email" />
            )}
          </div>
        )}

        <div className="mt-8">
          <div className="mb-3 text-sm font-medium text-ink">How would you like to respond?</div>
          <div className={cn("grid gap-3", GRID_COLS[modes.length])}>
            {modes.map((m) => {
              const meta = MODE_META[m];
              return (
                <button
                  key={m}
                  onClick={() => begin(m)}
                  disabled={!detailsValid || !!starting}
                  className="group flex items-center gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-left transition-all hover:border-cyan-400/40 hover:bg-white/[0.06] disabled:opacity-50 sm:flex-col sm:items-start"
                >
                  <span className="brand-bg flex h-10 w-10 items-center justify-center rounded-lg text-white">
                    <meta.icon className="h-5 w-5" />
                  </span>
                  <span>
                    <span className="block font-medium text-ink">{starting === m ? "Starting…" : meta.label}</span>
                    <span className="block text-xs text-ink-muted">{meta.description}</span>
                  </span>
                </button>
              );
            })}
          </div>
          {startError && <p className="mt-3 text-sm text-red-300">{startError}</p>}
        </div>
      </div>
    </Shell>
  );
}

export default function PublicSurveyPage() {
  return (
    <Suspense>
      <SurveyExperience />
    </Suspense>
  );
}
