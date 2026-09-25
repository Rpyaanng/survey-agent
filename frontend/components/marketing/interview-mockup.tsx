"use client";

import { motion } from "motion/react";
import { Check, Database } from "lucide-react";

// Adapted from med-doc-ai's landing ChatMockup: same visual language, now a
// general-purpose survey interview that shows answers becoming structured data.
const TURNS = [
  { from: "ai" as const, text: "Thanks for joining! On a scale of 1 to 5, how satisfied are you with onboarding so far?" },
  { from: "user" as const, text: "honestly like a 4, setup was quick but the import step confused me" },
  { from: "ai" as const, text: "Good to know. What was confusing about the import step?" },
  { from: "user" as const, text: "i couldn't tell if my columns mapped correctly" },
];

const CAPTURED = [
  { field: "satisfaction", value: "4 / 5" },
  { field: "pain_point", value: "Column mapping during import" },
];

export function InterviewMockup() {
  return (
    <div className="glass-panel w-full max-w-md rounded-2xl p-5 shadow-2xl sm:p-6">
      <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          {[0, 1, 2].map((i) => (
            <span key={i} className="h-2.5 w-2.5 rounded-full bg-white/20" />
          ))}
        </div>
        <span className="text-xs font-medium text-ink-faint">Onboarding feedback · AI chat</span>
      </div>
      <div className="space-y-3">
        {TURNS.map((turn, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.4, delay: i * 0.6 }}
            className={turn.from === "ai" ? "flex justify-start" : "flex justify-end"}
          >
            <div
              className={
                turn.from === "ai"
                  ? "max-w-[85%] rounded-2xl rounded-tl-sm border border-white/10 bg-white/[0.07] px-4 py-2.5 text-sm text-slate-200"
                  : "max-w-[85%] rounded-2xl rounded-tr-sm border border-cyan-400/25 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 px-4 py-2.5 text-sm text-cyan-50"
              }
            >
              {turn.text}
            </div>
          </motion.div>
        ))}
      </div>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: TURNS.length * 0.6 + 0.3 }}
        className="mt-5 space-y-2 border-t border-white/10 pt-4"
      >
        <div className="flex items-center gap-2 text-xs text-ink-faint">
          <Database className="h-3.5 w-3.5" /> Structured answers
        </div>
        {CAPTURED.map((c) => (
          <div key={c.field} className="flex items-center gap-2 text-xs">
            <Check className="h-3.5 w-3.5 text-emerald-400" />
            <code className="text-ink-faint">{c.field}</code>
            <span className="text-ink">{c.value}</span>
          </div>
        ))}
      </motion.div>
    </div>
  );
}
