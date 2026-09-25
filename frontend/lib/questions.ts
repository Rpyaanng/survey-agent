import {
  AlignLeft,
  AtSign,
  Calendar,
  CheckSquare,
  CircleDot,
  Clock,
  Gauge,
  Hash,
  ListFilter,
  Phone,
  Star,
  ThumbsUp,
  Type,
  type LucideIcon,
} from "lucide-react";
import type { Question, QuestionType } from "./types";

export const QUESTION_TYPES: { type: QuestionType; label: string; icon: LucideIcon; group: string }[] = [
  { type: "short_text", label: "Short text", icon: Type, group: "Text" },
  { type: "long_text", label: "Long text", icon: AlignLeft, group: "Text" },
  { type: "single_choice", label: "Single choice", icon: CircleDot, group: "Choice" },
  { type: "multiple_choice", label: "Multiple choice", icon: CheckSquare, group: "Choice" },
  { type: "dropdown", label: "Dropdown", icon: ListFilter, group: "Choice" },
  { type: "yes_no", label: "Yes / No", icon: ThumbsUp, group: "Choice" },
  { type: "rating", label: "Rating scale", icon: Star, group: "Scale" },
  { type: "nps", label: "Net Promoter Score", icon: Gauge, group: "Scale" },
  { type: "number", label: "Number", icon: Hash, group: "Data" },
  { type: "email", label: "Email", icon: AtSign, group: "Data" },
  { type: "phone", label: "Phone", icon: Phone, group: "Data" },
  { type: "date", label: "Date", icon: Calendar, group: "Data" },
  { type: "time", label: "Time", icon: Clock, group: "Data" },
];

export const TYPE_META = Object.fromEntries(QUESTION_TYPES.map((t) => [t.type, t])) as Record<
  QuestionType,
  (typeof QUESTION_TYPES)[number]
>;

export const hasChoices = (type: QuestionType) => type === "single_choice" || type === "multiple_choice" || type === "dropdown";

export function blankQuestion(type: QuestionType): Question {
  return withTypeDefaults({ type, title: "", description: "", required: false, options: {} });
}

/** Adjust options when a question's type changes, keeping what still applies. */
export function withTypeDefaults(q: Question): Question {
  const options = { ...q.options };
  if (hasChoices(q.type)) {
    if (!options.choices || options.choices.length < 2) options.choices = ["Option 1", "Option 2"];
  } else {
    delete options.choices;
    delete options.allow_other;
  }
  if (q.type === "rating") {
    options.min = options.min ?? 1;
    options.max = options.max ?? 5;
  } else if (q.type === "nps") {
    options.min = 0;
    options.max = 10;
  } else {
    delete options.min;
    delete options.max;
    delete options.min_label;
    delete options.max_label;
  }
  return { ...q, options };
}
