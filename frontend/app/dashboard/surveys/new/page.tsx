"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileUp, Link2, PenLine, Sparkles, Upload } from "lucide-react";
import { Field, PageHeader, UpgradeCallout, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { Survey } from "@/lib/types";

type Method = "ai" | "blank" | "google" | "pdf";

const METHODS: { id: Method; title: string; description: string; icon: typeof Sparkles; pro?: boolean }[] = [
  { id: "ai", title: "Describe it to AI", description: "Write a brief; get a methodologically sound draft.", icon: Sparkles },
  { id: "blank", title: "Start from scratch", description: "Build question by question in the editor.", icon: PenLine },
  { id: "google", title: "Import Google Form", description: "Bring an existing form's questions over in one click.", icon: Link2, pro: true },
  { id: "pdf", title: "Import a PDF form", description: "AI turns a paper or fillable PDF into a survey.", icon: FileUp, pro: true },
];

const EXAMPLES = [
  "Post-purchase satisfaction survey for an online furniture store",
  "Quarterly employee engagement pulse for a 200-person company",
  "Patient experience feedback after a clinic visit",
  "Event feedback for a two-day developer conference",
];

export default function NewSurveyPage() {
  const router = useRouter();
  const { org } = useSession();
  const [method, setMethod] = useState<Method>("ai");
  const [busy, setBusy] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(8);
  const [title, setTitle] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const isFree = org?.plan === "free";

  async function create() {
    setBusy(true);
    try {
      let survey: Survey;
      if (method === "ai") {
        survey = await api<Survey>("/surveys/generate", { method: "POST", body: { prompt, question_count: count } });
      } else if (method === "blank") {
        survey = await api<Survey>("/surveys", { method: "POST", body: { title: title || "Untitled survey" } });
      } else if (method === "google") {
        survey = await api<Survey>("/surveys/import/google-form", { method: "POST", body: { url: formUrl } });
      } else {
        const data = new FormData();
        data.append("file", file!);
        survey = await api<Survey>("/surveys/import/pdf", { method: "POST", body: data });
      }
      router.push(`/dashboard/surveys/${survey.id}`);
    } catch (err) {
      notifyError(err);
      setBusy(false);
    }
  }

  const ready =
    (method === "ai" && prompt.trim().length >= 10) ||
    method === "blank" ||
    (method === "google" && /^https:\/\/(docs\.google\.com\/forms|forms\.gle)\//.test(formUrl)) ||
    (method === "pdf" && !!file);
  const selected = METHODS.find((m) => m.id === method)!;
  const locked = selected.pro && isFree;

  return (
    <>
      <PageHeader title="Create a survey" description="Pick a starting point. You can edit everything afterwards." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {METHODS.map((m) => (
          <button
            key={m.id}
            onClick={() => setMethod(m.id)}
            className={cn(
              "glass-panel rounded-xl p-5 text-left transition-all",
              method === m.id ? "ring-glow border-cyan-400/40" : "glass-hover",
            )}
          >
            <div className="flex items-center justify-between">
              <m.icon className={cn("h-5 w-5", method === m.id ? "text-cyan-400" : "text-ink-faint")} />
              {m.pro && isFree && <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-300">Pro</span>}
            </div>
            <div className="mt-4 font-medium text-ink">{m.title}</div>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">{m.description}</p>
          </button>
        ))}
      </div>

      <div className="glass-panel mt-6 rounded-2xl p-6 sm:p-8">
        {locked ? (
          <UpgradeCallout feature={selected.title} />
        ) : method === "ai" ? (
          <div className="space-y-5">
            <Field label="What do you want to learn?" htmlFor="prompt" hint="Include the audience, goals, and anything you must ask.">
              <Textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={5}
                placeholder="e.g. Understand why trial users don't convert to paid. Audience: small-business owners who signed up in the last 30 days…"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setPrompt(ex)}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-ink-muted transition-colors hover:border-cyan-400/30 hover:text-ink"
                >
                  {ex}
                </button>
              ))}
            </div>
            <Field label={`About ${count} questions`} htmlFor="count">
              <input
                id="count"
                type="range"
                min={3}
                max={20}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full max-w-sm accent-cyan-400"
              />
            </Field>
          </div>
        ) : method === "blank" ? (
          <Field label="Survey title" htmlFor="title">
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Customer satisfaction survey" autoFocus />
          </Field>
        ) : method === "google" ? (
          <Field
            label="Google Form link"
            htmlFor="url"
            hint="The form must be public. We copy its questions into a new survey and collect all responses in Survey Agent."
          >
            <Input id="url" type="url" value={formUrl} onChange={(e) => setFormUrl(e.target.value)} placeholder="https://docs.google.com/forms/d/e/…/viewform" />
          </Field>
        ) : (
          <div
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const dropped = e.dataTransfer.files[0];
              if (dropped?.type === "application/pdf") setFile(dropped);
            }}
            className="flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-white/15 px-6 py-12 text-center transition-colors hover:border-cyan-400/40 hover:bg-white/[0.02]"
          >
            <Upload className="h-8 w-8 text-cyan-400" />
            <p className="mt-3 font-medium text-ink">{file ? file.name : "Drop a PDF here or click to browse"}</p>
            <p className="mt-1 text-xs text-ink-faint">Up to 10 MB and 60 pages. Text-based or fillable PDFs work best.</p>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        )}

        {!locked && (
          <div className="mt-8 flex items-center justify-end gap-3">
            {busy && method !== "blank" && <span className="text-sm text-ink-muted">This can take up to a minute…</span>}
            <Button size="lg" onClick={create} disabled={!ready} loading={busy}>
              {method === "ai" ? "Generate survey" : method === "blank" ? "Create survey" : "Import"}
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
