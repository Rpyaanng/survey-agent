import Link from "next/link";
import {
  ArrowRight,
  AudioLines,
  BarChart3,
  ClipboardList,
  FileUp,
  Globe,
  KeyRound,
  Link2,
  MessageSquareText,
  PhoneOutgoing,
  ShieldCheck,
  Sparkles,
  Users,
  Webhook,
} from "lucide-react";
import { InterviewMockup } from "@/components/marketing/interview-mockup";
import { Reveal } from "@/components/marketing/reveal";
import { Button } from "@/components/ui/button";

const CHANNELS = [
  { icon: ClipboardList, title: "Web form", body: "A fast, accessible one-page form for respondents who just want to click through." },
  { icon: MessageSquareText, title: "AI chat", body: "An interviewer that asks one question at a time, probes vague answers, and keeps people engaged." },
  { icon: AudioLines, title: "Browser voice", body: "Respondents talk instead of type. Well suited to mobile, accessibility, and long open-ended answers." },
  { icon: PhoneOutgoing, title: "Outbound phone", body: "Upload a contact list and the voice agent calls, interviews, and files the results." },
];

const STEPS = [
  { n: "01", title: "Build in minutes", body: "Describe your research goal to AI, import a Google Form or PDF, or build question by question." },
  { n: "02", title: "Launch everywhere", body: "One link serves form, chat and voice. Embed it, QR it, or have the agent phone your list." },
  { n: "03", title: "Get clean data", body: "Every answer is validated against its question type, so charts, exports and webhooks just work." },
];

const FEATURES = [
  { icon: Sparkles, title: "AI survey builder", body: "Methodologically sound drafts with neutral wording and the right question types." },
  { icon: Link2, title: "Google Forms import", body: "Bring existing forms over in one click and collect every response here." },
  { icon: FileUp, title: "PDF form import", body: "Turn paper or fillable PDF forms into conversational surveys." },
  { icon: BarChart3, title: "Analytics & AI insights", body: "NPS, distributions, completion funnels, and an executive summary of open-text themes." },
  { icon: Users, title: "Teams & roles", body: "Owner, admin, editor and viewer roles across multiple workspaces." },
  { icon: Webhook, title: "Webhooks", body: "Signed, real-time events to your CRM, warehouse or automation stack." },
  { icon: KeyRound, title: "REST API", body: "Workspace API keys for programmatic survey management and data access." },
  { icon: Globe, title: "Your brand", body: "Custom logo and color on survey pages. Remove our branding on paid plans." },
  { icon: ShieldCheck, title: "Built for trust", body: "Tenant isolation, signed webhooks, hashed credentials, and formula-safe exports." },
];

export default function LandingPage() {
  return (
    <>
      <section className="relative overflow-hidden px-4 pb-24 pt-32 sm:px-6 sm:pb-32 sm:pt-40 lg:px-8">
        <div className="aurora absolute inset-0 -z-10" aria-hidden />
        <div className="grid-fade absolute inset-0 -z-10" aria-hidden />
        <div className="mx-auto grid max-w-7xl items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-12">
          <div className="space-y-8">
            <Reveal>
              <div className="glass-panel inline-flex items-center gap-2 rounded-full px-3.5 py-1.5">
                <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-xs font-medium text-slate-300">Forms, AI chat, voice and phone, from one survey</span>
              </div>
            </Reveal>
            <Reveal delay={0.08}>
              <h1 className="font-display text-4xl font-extrabold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
                Surveys people <span className="text-gradient-accent">actually finish.</span>
              </h1>
            </Reveal>
            <Reveal delay={0.16}>
              <p className="max-w-xl text-lg leading-relaxed text-ink-muted">
                Survey Agent runs your questionnaire as a natural conversation, by text or voice, and turns every reply into clean,
                structured data. More completions, richer answers, zero manual cleanup.
              </p>
            </Reveal>
            <Reveal delay={0.24}>
              <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                <Button asChild size="lg">
                  <Link href="/signup">
                    Start free <ArrowRight />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="secondary">
                  <Link href="/pricing">See pricing</Link>
                </Button>
              </div>
            </Reveal>
            <Reveal delay={0.32}>
              <p className="text-sm text-ink-faint">Free plan available · No credit card required</p>
            </Reveal>
          </div>
          <Reveal delay={0.2} className="flex w-full justify-center lg:block lg:justify-self-end">
            <div className="relative animate-drift">
              <div className="gradient-accent absolute -inset-8 -z-10 rounded-full opacity-[0.18] blur-3xl" aria-hidden />
              <InterviewMockup />
            </div>
          </Reveal>
        </div>
      </section>

      <section id="channels" className="relative bg-ground-raised/60 px-4 py-24 sm:px-6 lg:px-8">
        <div className="seam-top absolute inset-x-0 top-0 h-px" aria-hidden />
        <div className="mx-auto max-w-7xl">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">One survey. Every channel.</h2>
            <p className="mt-4 text-lg text-ink-muted">Write your questions once. Respondents pick the way they like to answer, and results land in one place.</p>
          </Reveal>
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CHANNELS.map((c, i) => (
              <Reveal key={c.title} delay={i * 0.06}>
                <div className="glass-panel glass-hover h-full rounded-2xl p-6">
                  <span className="gradient-accent flex h-11 w-11 items-center justify-center rounded-xl">
                    <c.icon className="h-5 w-5 text-white" />
                  </span>
                  <h3 className="mt-5 font-display text-lg font-semibold">{c.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-muted">{c.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="px-4 py-24 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">From question to insight in three steps</h2>
          </Reveal>
          <div className="mt-14 grid gap-8 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 0.08}>
                <div className="border-t border-white/10 pt-6">
                  <span className="font-mono text-sm text-cyan-400">{s.n}</span>
                  <h3 className="mt-3 font-display text-xl font-semibold">{s.title}</h3>
                  <p className="mt-2 leading-relaxed text-ink-muted">{s.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="relative bg-ground-raised/60 px-4 py-24 sm:px-6 lg:px-8">
        <div className="seam-top absolute inset-x-0 top-0 h-px" aria-hidden />
        <div className="mx-auto max-w-7xl">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Everything professional survey teams need</h2>
          </Reveal>
          <div className="mt-14 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 0.06}>
                <div className="flex gap-4">
                  <f.icon className="mt-1 h-5 w-5 shrink-0 text-cyan-400" />
                  <div>
                    <h3 className="font-semibold text-ink">{f.title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-ink-muted">{f.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-24 sm:px-6 lg:px-8">
        <Reveal>
          <div className="glass-panel ring-glow relative mx-auto max-w-4xl overflow-hidden rounded-3xl px-8 py-16 text-center">
            <div className="aurora absolute inset-0 -z-10" aria-hidden />
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Launch your first conversational survey today</h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-ink-muted">Start on the free plan. Upgrade when you need voice, phone, imports and the API.</p>
            <div className="mt-8 flex justify-center gap-3">
              <Button asChild size="lg">
                <Link href="/signup">
                  Create free account <ArrowRight />
                </Link>
              </Button>
            </div>
          </div>
        </Reveal>
      </section>
    </>
  );
}
