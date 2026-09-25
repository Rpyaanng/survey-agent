import Link from "next/link";
import { FileText, Link2, MessageSquareText, Sparkles } from "lucide-react";
import type { Survey } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { SurveyStatusBadge } from "./shared";

const SOURCE_ICON = { manual: FileText, ai: Sparkles, pdf: FileText, google_form: Link2 } as const;

export function SurveyRow({ survey }: { survey: Survey }) {
  const Icon = SOURCE_ICON[survey.source?.type ?? "manual"] ?? FileText;
  const completed = survey.responses?.completed ?? 0;
  return (
    <Link
      href={`/dashboard/surveys/${survey.id}`}
      className="group glass-panel glass-hover flex items-center gap-4 rounded-xl px-5 py-4"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] text-ink-muted group-hover:text-cyan-400">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2.5">
          <span className="truncate font-medium text-ink">{survey.title}</span>
          <SurveyStatusBadge status={survey.status} />
        </div>
        <div className="mt-0.5 text-xs text-ink-faint">
          {survey.question_count} questions · updated {timeAgo(survey.updated_at)}
        </div>
      </div>
      <div className="hidden text-right sm:block">
        <div className="flex items-center justify-end gap-1.5 font-display text-lg font-semibold tabular-nums text-ink">
          <MessageSquareText className="h-4 w-4 text-ink-faint" />
          {completed.toLocaleString()}
        </div>
        <div className="text-xs text-ink-faint">responses</div>
      </div>
    </Link>
  );
}
