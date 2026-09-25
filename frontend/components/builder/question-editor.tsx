"use client";

import { ArrowDown, ArrowUp, Copy, GripVertical, Plus, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { QUESTION_TYPES, TYPE_META, hasChoices, withTypeDefaults } from "@/lib/questions";
import type { Question, QuestionType } from "@/lib/types";

interface Props {
  index: number;
  total: number;
  question: Question;
  readOnly?: boolean;
  onChange: (q: Question) => void;
  onMove: (delta: -1 | 1) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}

export function QuestionEditor({ index, total, question: q, readOnly, onChange, onMove, onDuplicate, onRemove }: Props) {
  const Icon = TYPE_META[q.type].icon;
  const set = (patch: Partial<Question>) => onChange({ ...q, ...patch });
  const setOptions = (patch: Partial<Question["options"]>) => onChange({ ...q, options: { ...q.options, ...patch } });
  const choices = q.options.choices ?? [];

  return (
    <div className="glass-panel group rounded-xl p-5">
      <div className="flex items-start gap-3">
        <div className="flex flex-col items-center gap-1 pt-2 text-ink-faint">
          <GripVertical className="h-4 w-4" />
          <span className="font-mono text-xs">{index + 1}</span>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={q.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="Type your question"
              className="h-11 flex-1 text-base font-medium"
              aria-label={`Question ${index + 1}`}
              disabled={readOnly}
            />
            <div className="relative sm:w-52">
              <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-400" />
              <Select
                value={q.type}
                onChange={(e) => onChange(withTypeDefaults({ ...q, type: e.target.value as QuestionType }))}
                className="h-11 pl-9"
                aria-label="Question type"
                disabled={readOnly}
              >
                {QUESTION_TYPES.map((t) => (
                  <option key={t.type} value={t.type}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <Textarea
            value={q.description}
            onChange={(e) => set({ description: e.target.value })}
            placeholder="Optional help text or context for the interviewer"
            className="min-h-0 text-sm"
            rows={1}
            disabled={readOnly}
          />

          {hasChoices(q.type) && (
            <div className="space-y-2">
              {choices.map((choice, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className={`h-3.5 w-3.5 shrink-0 border border-white/25 ${q.type === "multiple_choice" ? "rounded" : "rounded-full"}`} />
                  <Input
                    value={choice}
                    onChange={(e) => setOptions({ choices: choices.map((c, j) => (j === i ? e.target.value : c)) })}
                    className="h-9"
                    aria-label={`Choice ${i + 1}`}
                    disabled={readOnly}
                  />
                  {!readOnly && choices.length > 2 && (
                    <Button variant="ghost" size="icon" onClick={() => setOptions({ choices: choices.filter((_, j) => j !== i) })} aria-label="Remove choice">
                      <X />
                    </Button>
                  )}
                </div>
              ))}
              {!readOnly && (
                <div className="flex flex-wrap items-center gap-4 pt-1">
                  <Button variant="ghost" size="sm" onClick={() => setOptions({ choices: [...choices, `Option ${choices.length + 1}`] })}>
                    <Plus /> Add choice
                  </Button>
                  <label className="flex items-center gap-2 text-xs text-ink-muted">
                    <Switch checked={!!q.options.allow_other} onCheckedChange={(v) => setOptions({ allow_other: v })} />
                    Allow &ldquo;Other&rdquo; answers
                  </label>
                </div>
              )}
            </div>
          )}

          {(q.type === "rating" || q.type === "nps") && (
            <div className="grid gap-3 sm:grid-cols-4">
              {q.type === "rating" && (
                <>
                  <label className="space-y-1 text-xs text-ink-faint">
                    From
                    <Select value={q.options.min ?? 1} onChange={(e) => setOptions({ min: Number(e.target.value) })} className="h-9" disabled={readOnly}>
                      {[0, 1].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </Select>
                  </label>
                  <label className="space-y-1 text-xs text-ink-faint">
                    To
                    <Select value={q.options.max ?? 5} onChange={(e) => setOptions({ max: Number(e.target.value) })} className="h-9" disabled={readOnly}>
                      {[3, 4, 5, 6, 7, 10].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </Select>
                  </label>
                </>
              )}
              <label className="space-y-1 text-xs text-ink-faint">
                Low label
                <Input value={q.options.min_label ?? ""} onChange={(e) => setOptions({ min_label: e.target.value })} className="h-9" placeholder="e.g. Poor" disabled={readOnly} />
              </label>
              <label className="space-y-1 text-xs text-ink-faint">
                High label
                <Input value={q.options.max_label ?? ""} onChange={(e) => setOptions({ max_label: e.target.value })} className="h-9" placeholder="e.g. Excellent" disabled={readOnly} />
              </label>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-white/[0.06] pt-3">
            <label className="flex items-center gap-2 text-sm text-ink-muted">
              <Switch checked={q.required} onCheckedChange={(v) => set({ required: v })} disabled={readOnly} />
              Required
            </label>
            {!readOnly && (
              <div className="flex items-center gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
                <Button variant="ghost" size="icon" onClick={() => onMove(-1)} disabled={index === 0} aria-label="Move up">
                  <ArrowUp />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => onMove(1)} disabled={index === total - 1} aria-label="Move down">
                  <ArrowDown />
                </Button>
                <Button variant="ghost" size="icon" onClick={onDuplicate} aria-label="Duplicate question">
                  <Copy />
                </Button>
                <Button variant="ghost" size="icon" onClick={onRemove} aria-label="Delete question" className="hover:text-red-300">
                  <Trash2 />
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
