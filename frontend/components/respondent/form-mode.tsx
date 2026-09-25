"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/input";
import { ApiError, api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PublicSurvey, Question } from "@/lib/types";

type Value = string | number | boolean | string[] | undefined;

function ChoiceButton({ selected, onClick, multi, children }: { selected: boolean; onClick: () => void; multi?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role={multi ? "checkbox" : "radio"}
      aria-checked={selected}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-all",
        selected ? "border-cyan-400/60 bg-cyan-400/[0.08] text-ink" : "border-white/10 bg-white/[0.02] text-ink-muted hover:border-white/20 hover:bg-white/[0.04]",
      )}
    >
      <span
        className={cn(
          "flex h-4.5 w-4.5 shrink-0 items-center justify-center border",
          multi ? "rounded" : "rounded-full",
          selected ? "border-cyan-400 bg-cyan-400" : "border-white/30",
        )}
      >
        {selected && <span className={cn("bg-ground", multi ? "h-2 w-2 rounded-[1px]" : "h-1.5 w-1.5 rounded-full")} />}
      </span>
      {children}
    </button>
  );
}

export function QuestionInput({ question: q, value, onChange }: { question: Question; value: Value; onChange: (v: Value) => void }) {
  const opts = q.options ?? {};
  const choices = opts.choices ?? [];
  const id = `q-${q.id}`;
  switch (q.type) {
    case "long_text":
      return <Textarea id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} rows={4} />;
    case "single_choice":
      return (
        <div role="radiogroup" className="grid gap-2">
          {choices.map((c) => (
            <ChoiceButton key={c} selected={value === c} onClick={() => onChange(value === c ? undefined : c)}>
              {c}
            </ChoiceButton>
          ))}
        </div>
      );
    case "multiple_choice": {
      const selected = (value as string[]) ?? [];
      return (
        <div className="grid gap-2">
          {choices.map((c) => (
            <ChoiceButton
              key={c}
              multi
              selected={selected.includes(c)}
              onClick={() => onChange(selected.includes(c) ? selected.filter((s) => s !== c) : [...selected, c])}
            >
              {c}
            </ChoiceButton>
          ))}
        </div>
      );
    }
    case "dropdown":
      return (
        <Select id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">Select…</option>
          {choices.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </Select>
      );
    case "yes_no":
      return (
        <div role="radiogroup" className="grid grid-cols-2 gap-2">
          {[true, false].map((v) => (
            <ChoiceButton key={String(v)} selected={value === v} onClick={() => onChange(value === v ? undefined : v)}>
              {v ? "Yes" : "No"}
            </ChoiceButton>
          ))}
        </div>
      );
    case "rating":
    case "nps": {
      const lo = opts.min ?? (q.type === "nps" ? 0 : 1);
      const hi = opts.max ?? (q.type === "nps" ? 10 : 5);
      const nums = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
      return (
        <div>
          <div role="radiogroup" className="flex flex-wrap gap-1.5">
            {nums.map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={value === n}
                onClick={() => onChange(value === n ? undefined : n)}
                className={cn(
                  "h-11 min-w-11 flex-1 rounded-lg border text-sm font-semibold tabular-nums transition-all",
                  value === n ? "border-cyan-400 bg-cyan-400 text-ground" : "border-white/10 bg-white/[0.03] text-ink-muted hover:border-white/25",
                )}
              >
                {n}
              </button>
            ))}
          </div>
          {(opts.min_label || opts.max_label) && (
            <div className="mt-2 flex justify-between text-xs text-ink-faint">
              <span>{opts.min_label}</span>
              <span>{opts.max_label}</span>
            </div>
          )}
        </div>
      );
    }
    case "number":
      return <Input id={id} type="number" inputMode="decimal" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} className="max-w-48" />;
    case "email":
      return <Input id={id} type="email" autoComplete="email" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
    case "phone":
      return <Input id={id} type="tel" autoComplete="tel" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
    case "date":
      return <Input id={id} type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} className="max-w-56" />;
    case "time":
      return <Input id={id} type="time" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} className="max-w-40" />;
    default:
      return <Input id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

const isEmpty = (v: Value) => v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

export function FormMode({ survey, responseId, responseToken, onDone }: { survey: PublicSurvey; responseId: string; responseToken: string; onDone: () => void }) {
  const [values, setValues] = useState<Record<string, Value>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const answered = survey.questions.filter((q) => !isEmpty(values[q.id!])).length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const missing = Object.fromEntries(
      survey.questions.filter((q) => q.required && isEmpty(values[q.id!])).map((q) => [q.id!, "This question is required"]),
    );
    setErrors(missing);
    if (Object.keys(missing).length) {
      document.getElementById(`field-${Object.keys(missing)[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const answers = Object.fromEntries(Object.entries(values).filter(([, v]) => !isEmpty(v)));
      await api(`/public/responses/${responseId}/answers`, { method: "POST", body: { answers, complete: true }, responseToken });
      onDone();
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error" && err.details && !Array.isArray(err.details)) {
        setErrors(err.details as Record<string, string>);
      } else {
        setFormError(errorMessage(err));
      }
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="sticky top-0 z-10 -mx-1 bg-ground/80 px-1 py-3 backdrop-blur">
        <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
          <div className="brand-bg h-full rounded-full transition-all duration-500" style={{ width: `${(answered / Math.max(1, survey.questions.length)) * 100}%` }} />
        </div>
      </div>
      {survey.questions.map((q, i) => (
        <fieldset key={q.id} id={`field-${q.id}`} className={cn("glass-panel rounded-2xl p-5 sm:p-6", errors[q.id!] && "border-red-400/40")}>
          <legend className="sr-only">{q.title}</legend>
          <label htmlFor={`q-${q.id}`} className="block">
            <span className="text-xs font-medium text-ink-faint">
              {i + 1} / {survey.questions.length}
            </span>
            <span className="mt-1 block text-base font-medium leading-snug text-ink">
              {q.title}
              {q.required && <span className="ml-1 text-cyan-400">*</span>}
            </span>
            {q.description && <span className="mt-1 block text-sm text-ink-muted">{q.description}</span>}
          </label>
          <div className="mt-4">
            <QuestionInput question={q} value={values[q.id!]} onChange={(v) => setValues((prev) => ({ ...prev, [q.id!]: v }))} />
          </div>
          {errors[q.id!] && <p className="mt-2 text-sm text-red-300">{errors[q.id!]}</p>}
        </fieldset>
      ))}
      {formError && <p className="text-sm text-red-300">{formError}</p>}
      <div className="flex items-center justify-between pt-2">
        <span className="text-sm text-ink-faint">
          <CheckCircle2 className="mr-1 inline h-4 w-4" />
          {answered} of {survey.questions.length} answered
        </span>
        <Button type="submit" size="lg" loading={submitting}>
          Submit
        </Button>
      </div>
    </form>
  );
}
