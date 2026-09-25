"use client";

import { useEffect, useState } from "react";
import { AudioLines, ClipboardList, MessageSquareText } from "lucide-react";
import { toast } from "sonner";
import { Field, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useSurvey } from "@/lib/use-survey";
import { cn } from "@/lib/utils";
import type { Mode, Survey, SurveySettings, Tone } from "@/lib/types";

const MODES: { id: Mode; label: string; description: string; icon: typeof ClipboardList; plan?: string }[] = [
  { id: "form", label: "Web form", description: "Classic one-page form. Fast for short surveys.", icon: ClipboardList },
  { id: "chat", label: "AI chat", description: "An AI interviewer asks questions one at a time and follows up.", icon: MessageSquareText },
  { id: "voice", label: "Voice", description: "Respondents talk to the interviewer in the browser.", icon: AudioLines, plan: "Pro" },
];

const TONES: { id: Tone; label: string }[] = [
  { id: "friendly", label: "Friendly" },
  { id: "professional", label: "Professional" },
  { id: "empathetic", label: "Empathetic (sensitive topics)" },
  { id: "playful", label: "Playful" },
  { id: "concise", label: "Concise" },
];

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-b border-white/[0.06] py-8 first:pt-0 last:border-0 lg:grid-cols-[240px_1fr]">
      <div>
        <h2 className="font-display text-base font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  );
}

export default function SurveySettingsPage() {
  const { id, survey, mutate } = useSurvey();
  const { org, can } = useSession();
  const [settings, setSettings] = useState<SurveySettings | null>(null);
  const [emails, setEmails] = useState("");
  const [saving, setSaving] = useState(false);
  const isFree = org?.plan === "free";
  const readOnly = !can("editor");

  useEffect(() => {
    if (survey && !settings) {
      setSettings(survey.settings);
      setEmails(survey.settings.notify_emails.join(", "));
    }
  }, [survey, settings]);

  if (!survey || !settings) return <Skeleton className="h-96 rounded-xl" />;

  const set = (patch: Partial<SurveySettings>) => setSettings({ ...settings, ...patch });
  const toggleMode = (mode: Mode) => {
    const has = settings.modes.includes(mode);
    if (has && settings.modes.length === 1) return toast.error("Keep at least one response mode enabled");
    set({ modes: has ? settings.modes.filter((m) => m !== mode) : [...settings.modes, mode] });
  };

  async function save() {
    setSaving(true);
    try {
      const notify_emails = emails
        .split(/[,\s]+/)
        .map((e) => e.trim())
        .filter(Boolean);
      const updated = await api<Survey>(`/surveys/${id}`, { method: "PATCH", body: { settings: { ...settings, notify_emails } } });
      await mutate(updated, { revalidate: false });
      setSettings(updated.settings);
      toast.success("Settings saved");
    } catch (err) {
      notifyError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="glass-panel rounded-2xl p-6 sm:p-8">
      <fieldset disabled={readOnly} className="contents">
        <Section title="Response modes" description="How respondents can take this survey. They choose when they open the link.">
          <div className="grid gap-3 sm:grid-cols-3">
            {MODES.map((m) => {
              const locked = m.plan && isFree;
              const active = settings.modes.includes(m.id);
              return (
                <button
                  key={m.id}
                  type="button"
                  disabled={!!locked || readOnly}
                  onClick={() => toggleMode(m.id)}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-all disabled:cursor-not-allowed",
                    active ? "border-cyan-400/40 bg-cyan-400/[0.06]" : "border-white/10 bg-white/[0.02] hover:bg-white/[0.04]",
                    locked && "opacity-60",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <m.icon className={cn("h-5 w-5", active ? "text-cyan-400" : "text-ink-faint")} />
                    {locked ? (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-300">{m.plan}</span>
                    ) : (
                      <span className={cn("h-4 w-4 rounded-full border", active ? "border-cyan-400 bg-cyan-400" : "border-white/25")} />
                    )}
                  </div>
                  <div className="mt-3 text-sm font-medium text-ink">{m.label}</div>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">{m.description}</p>
                </button>
              );
            })}
          </div>
        </Section>

        <Section title="AI interviewer" description="The persona used for chat, voice and phone interviews.">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Interviewer name" htmlFor="agent-name">
              <Input id="agent-name" value={settings.agent.name} onChange={(e) => set({ agent: { ...settings.agent, name: e.target.value } })} maxLength={40} />
            </Field>
            <Field label="Tone" htmlFor="agent-tone">
              <Select id="agent-tone" value={settings.agent.tone} onChange={(e) => set({ agent: { ...settings.agent, tone: e.target.value as Tone } })}>
                {TONES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Welcome message" htmlFor="welcome" hint="Shown on the form and paraphrased by the interviewer.">
            <Textarea id="welcome" rows={2} value={settings.welcome_message} onChange={(e) => set({ welcome_message: e.target.value })} />
          </Field>
          <Field label="Closing message" htmlFor="closing">
            <Textarea id="closing" rows={2} value={settings.closing_message} onChange={(e) => set({ closing_message: e.target.value })} />
          </Field>
          <Field
            label="Extra instructions"
            htmlFor="instructions"
            hint="e.g. “If someone mentions a bug, ask which device they use.” Respondents never see this."
          >
            <Textarea
              id="instructions"
              rows={3}
              value={settings.agent.instructions}
              onChange={(e) => set({ agent: { ...settings.agent, instructions: e.target.value } })}
              maxLength={2000}
            />
          </Field>
        </Section>

        <Section title="Collection" description="Limits and respondent details.">
          <div className="flex flex-col gap-3">
            <label className="flex items-center gap-3 text-sm text-ink-muted">
              <Switch checked={settings.collect.name} onCheckedChange={(v) => set({ collect: { ...settings.collect, name: v } })} />
              Ask for the respondent&apos;s name before starting
            </label>
            <label className="flex items-center gap-3 text-sm text-ink-muted">
              <Switch checked={settings.collect.email} onCheckedChange={(v) => set({ collect: { ...settings.collect, email: v } })} />
              Ask for the respondent&apos;s email before starting
            </label>
          </div>
          <Field label="Response limit" htmlFor="limit" hint="The survey closes automatically after this many completed responses.">
            <Input
              id="limit"
              type="number"
              min={1}
              value={settings.response_limit ?? ""}
              onChange={(e) => set({ response_limit: e.target.value ? Number(e.target.value) : null })}
              placeholder="No limit"
              className="max-w-40"
            />
          </Field>
        </Section>

        <Section title="Notifications & branding" description="Who hears about new responses and how the survey looks.">
          <Field label="Email me on each response" htmlFor="emails" hint="Comma-separated, up to 10 addresses.">
            <Input id="emails" value={emails} onChange={(e) => setEmails(e.target.value)} placeholder="you@company.com, team@company.com" />
          </Field>
          <label className={cn("flex items-center gap-3 text-sm text-ink-muted", isFree && "opacity-60")}>
            <Switch checked={settings.show_branding || isFree} disabled={isFree} onCheckedChange={(v) => set({ show_branding: v })} />
            Show &ldquo;Powered by Survey Agent&rdquo;
            {isFree && <span className="text-xs text-violet-300">Pro plan to remove</span>}
          </label>
        </Section>
      </fieldset>

      {!readOnly && (
        <div className="flex justify-end pt-4">
          <Button onClick={save} loading={saving}>
            Save settings
          </Button>
        </div>
      )}
    </div>
  );
}
