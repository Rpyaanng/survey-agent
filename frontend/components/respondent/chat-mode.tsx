"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PublicSurvey, TranscriptTurn } from "@/lib/types";

interface TurnResult {
  reply: string;
  completed: boolean;
  progress: { answered: number; total: number };
  transcript: TranscriptTurn[];
}

function TypingDots() {
  return (
    <span className="flex gap-1 py-1">
      {[0, 150, 300].map((delay) => (
        <span key={delay} className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-400" style={{ animationDelay: `${delay}ms` }} />
      ))}
    </span>
  );
}

export function ChatMode({ survey, responseId, responseToken, onDone }: { survey: PublicSurvey; responseId: string; responseToken: string; onDone: () => void }) {
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [input, setInput] = useState("");
  const [waiting, setWaiting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ answered: 0, total: survey.questions.length });
  const [completed, setCompleted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const started = useRef(false);

  async function send(message: string | null) {
    setWaiting(true);
    setError(null);
    try {
      const result = await api<TurnResult>(`/public/responses/${responseId}/chat`, { method: "POST", body: { message }, responseToken });
      setTurns(result.transcript);
      setProgress(result.progress);
      if (result.completed) {
        setCompleted(true);
        setTimeout(onDone, 2500);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setWaiting(false);
      inputRef.current?.focus();
    }
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    send(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, waiting]);

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || waiting || completed) return;
    setTurns((prev) => [...prev, { role: "respondent", text }]);
    setInput("");
    send(text);
  }

  return (
    <div className="flex h-[min(720px,calc(100dvh-10rem))] flex-col overflow-hidden rounded-2xl glass-panel">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="brand-bg flex h-8 w-8 items-center justify-center rounded-full">
            <Bot className="h-4 w-4 text-white" />
          </span>
          <div>
            <div className="text-sm font-medium text-ink">{survey.agent_name}</div>
            <div className="text-xs text-ink-faint">{waiting ? "typing…" : "AI interviewer"}</div>
          </div>
        </div>
        <div className="text-right text-xs text-ink-faint">
          <div className="tabular-nums">
            {progress.answered} / {progress.total}
          </div>
          <div className="mt-1 h-1 w-24 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="brand-bg h-full transition-all duration-500" style={{ width: `${(progress.answered / Math.max(1, progress.total)) * 100}%` }} />
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6 sm:px-6" aria-live="polite">
        {turns.map((turn, i) => (
          <div key={i} className={cn("flex", turn.role === "respondent" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap",
                turn.role === "respondent"
                  ? "rounded-br-sm border border-cyan-400/25 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 text-cyan-50"
                  : "rounded-bl-sm border border-white/10 bg-white/[0.05] text-slate-200",
              )}
            >
              {turn.text}
            </div>
          </div>
        ))}
        {waiting && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.05] px-4 py-2.5">
              <TypingDots />
            </div>
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}{" "}
            <button className="underline" onClick={() => send(turns.at(-1)?.role === "respondent" ? turns.at(-1)!.text : null)}>
              Retry
            </button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={submit} className="border-t border-white/[0.06] p-3">
        <div className="flex items-end gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-1.5 focus-within:border-cyan-400/40">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={2000}
            disabled={completed}
            placeholder={completed ? "Thanks! Wrapping up…" : "Type your answer…"}
            aria-label="Your answer"
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || waiting || completed}
            aria-label="Send"
            className="brand-bg flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white transition-opacity disabled:opacity-30"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
