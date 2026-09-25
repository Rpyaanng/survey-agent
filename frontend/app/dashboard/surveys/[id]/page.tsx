"use client";

import { useEffect, useRef, useState } from "react";
import { ListPlus, Plus, Save } from "lucide-react";
import { toast } from "sonner";
import { QuestionEditor } from "@/components/builder/question-editor";
import { EmptyState, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { QUESTION_TYPES, blankQuestion } from "@/lib/questions";
import { useSession } from "@/lib/session";
import { useSurvey } from "@/lib/use-survey";
import type { Question, QuestionType, Survey } from "@/lib/types";

type Draft = Question & { _key: string };

let keySeq = 0;
const withKey = (q: Question): Draft => ({ ...q, _key: q.id ?? `new-${++keySeq}` });

function AddQuestionMenu({ onAdd, children }: { onAdd: (t: QuestionType) => void; children: React.ReactNode }) {
  const groups = [...new Set(QUESTION_TYPES.map((t) => t.group))];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent className="w-56 border-white/10 bg-popover" align="start">
        {groups.map((group) => (
          <div key={group}>
            <DropdownMenuLabel className="text-[11px] uppercase tracking-wider text-ink-faint">{group}</DropdownMenuLabel>
            {QUESTION_TYPES.filter((t) => t.group === group).map((t) => (
              <DropdownMenuItem key={t.type} onClick={() => onAdd(t.type)} className="gap-2">
                <t.icon className="h-4 w-4 text-cyan-400" /> {t.label}
              </DropdownMenuItem>
            ))}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function BuilderPage() {
  const { id, survey, mutate } = useSurvey();
  const { can } = useSession();
  const readOnly = !can("editor");
  const [questions, setQuestions] = useState<Draft[] | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const loadedFor = useRef<string | null>(null);

  // Seed local state once per survey; later SWR refreshes must not clobber unsaved edits.
  useEffect(() => {
    if (survey && loadedFor.current !== survey.id) {
      loadedFor.current = survey.id;
      setQuestions((survey.questions ?? []).map(withKey));
      setTitle(survey.title);
      setDescription(survey.description);
    }
  }, [survey]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function update(next: Draft[]) {
    setQuestions(next);
    setDirty(true);
  }

  async function save() {
    if (!questions) return;
    const empty = questions.findIndex((q) => !q.title.trim());
    if (empty >= 0) {
      toast.error(`Question ${empty + 1} needs a title`);
      return;
    }
    setSaving(true);
    try {
      if (title !== survey?.title || description !== survey?.description) {
        await api(`/surveys/${id}`, { method: "PATCH", body: { title: title.trim() || "Untitled survey", description } });
      }
      const saved = await api<Survey>(`/surveys/${id}/questions`, {
        method: "PUT",
        body: { questions: questions.map(({ _key, position, ...q }) => q) },
      });
      setQuestions((saved.questions ?? []).map(withKey));
      await mutate(saved, { revalidate: false });
      setDirty(false);
      toast.success("Survey saved");
    } catch (err) {
      notifyError(err);
    } finally {
      setSaving(false);
    }
  }

  if (!survey || !questions) {
    return (
      <div className="space-y-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-40 rounded-xl" />
        ))}
      </div>
    );
  }

  const add = (type: QuestionType) => update([...questions, withKey(blankQuestion(type))]);

  return (
    <div className="grid gap-8 xl:grid-cols-[1fr_260px]">
      <div className="space-y-4">
        <div className="glass-panel space-y-3 rounded-xl p-5">
          <Input
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setDirty(true);
            }}
            className="h-12 border-transparent bg-transparent px-0 font-display text-xl font-bold focus:ring-0"
            aria-label="Survey title"
            disabled={readOnly}
          />
          <Textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setDirty(true);
            }}
            placeholder="Describe the purpose of this survey. Respondents and the AI interviewer both see this."
            rows={2}
            disabled={readOnly}
          />
        </div>

        {questions.length === 0 ? (
          <EmptyState
            icon={<ListPlus />}
            title="No questions yet"
            description="Add your first question to get started."
            action={
              !readOnly && (
                <AddQuestionMenu onAdd={add}>
                  <Button>
                    <Plus /> Add question
                  </Button>
                </AddQuestionMenu>
              )
            }
          />
        ) : (
          questions.map((q, i) => (
            <QuestionEditor
              key={q._key}
              index={i}
              total={questions.length}
              question={q}
              readOnly={readOnly}
              onChange={(next) => update(questions.map((item, j) => (j === i ? { ...next, _key: item._key } : item)))}
              onMove={(delta) => {
                const next = [...questions];
                [next[i], next[i + delta]] = [next[i + delta], next[i]];
                update(next);
              }}
              onDuplicate={() => {
                const { id: _id, _key, ...rest } = q;
                const next = [...questions];
                next.splice(i + 1, 0, withKey({ ...rest, title: `${q.title} (copy)` }));
                update(next);
              }}
              onRemove={() => update(questions.filter((_, j) => j !== i))}
            />
          ))
        )}

        {!readOnly && questions.length > 0 && (
          <AddQuestionMenu onAdd={add}>
            <button className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 py-4 text-sm font-medium text-ink-muted transition-colors hover:border-cyan-400/40 hover:text-ink">
              <Plus className="h-4 w-4" /> Add question
            </button>
          </AddQuestionMenu>
        )}
      </div>

      <aside className="space-y-4 xl:sticky xl:top-8 xl:h-fit">
        {!readOnly && (
          <div className="glass-panel rounded-xl p-5">
            <Button className="w-full" onClick={save} loading={saving} disabled={!dirty}>
              <Save /> {dirty ? "Save changes" : "All changes saved"}
            </Button>
            {survey.status === "published" && dirty && (
              <p className="mt-3 text-xs text-amber-300/90">This survey is live. Changes apply to new respondents right away.</p>
            )}
          </div>
        )}
        <div className="glass-panel rounded-xl p-5 text-sm">
          <h3 className="font-medium text-ink">Tips</h3>
          <ul className="mt-3 list-disc space-y-2 pl-4 text-xs leading-relaxed text-ink-muted">
            <li>Every question works in form, chat, voice and phone modes. The AI interviewer rephrases them conversationally.</li>
            <li>Use help text to give the interviewer context, like why you ask or what counts as a complete answer.</li>
            <li>Removing a question that already has answers archives it, so past responses and exports keep their data.</li>
          </ul>
          {survey.source?.type === "google_form" && (
            <p className="mt-4 rounded-lg bg-white/[0.04] p-3 text-xs text-ink-muted">
              Imported from Google Forms. Responses are collected here in Survey Agent. The original form isn&apos;t changed.
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
