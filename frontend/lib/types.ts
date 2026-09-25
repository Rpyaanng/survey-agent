// Mirrors the Flask API's JSON shapes (see backend/survey_agent/models + api).

export type Role = "owner" | "admin" | "editor" | "viewer";
export type PlanId = "free" | "pro" | "team" | "enterprise";

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: Role;
  plan: PlanId;
  branding: { logo_url?: string; primary_color?: string };
  created_at: string;
}

export interface Session {
  user: User;
  organizations: Organization[];
  default_org_id: string | null;
}

export type QuestionType =
  | "short_text"
  | "long_text"
  | "single_choice"
  | "multiple_choice"
  | "dropdown"
  | "rating"
  | "nps"
  | "yes_no"
  | "number"
  | "email"
  | "phone"
  | "date"
  | "time";

export interface QuestionOptions {
  choices?: string[];
  allow_other?: boolean;
  min?: number;
  max?: number;
  min_label?: string;
  max_label?: string;
}

export interface Question {
  id?: string;
  position?: number;
  type: QuestionType;
  title: string;
  description: string;
  required: boolean;
  options: QuestionOptions;
}

export type Mode = "form" | "chat" | "voice";
export type Tone = "friendly" | "professional" | "playful" | "empathetic" | "concise";

export interface SurveySettings {
  modes: Mode[];
  welcome_message: string;
  closing_message: string;
  agent: { name: string; tone: Tone; instructions: string };
  collect: { name: boolean; email: boolean };
  response_limit: number | null;
  notify_emails: string[];
  show_branding: boolean;
  language: string;
}

export type SurveyStatus = "draft" | "published" | "closed";

export interface Survey {
  id: string;
  title: string;
  description: string;
  status: SurveyStatus;
  public_token: string;
  settings: SurveySettings;
  source: { type: "manual" | "ai" | "pdf" | "google_form"; url?: string; filename?: string; prompt?: string };
  created_at: string;
  updated_at: string;
  published_at: string | null;
  closed_at: string | null;
  question_count: number;
  questions?: Question[];
  responses?: { completed: number; in_progress: number; total: number };
}

export type Channel = "form" | "chat" | "voice" | "phone" | "api";
export type ResponseStatus = "in_progress" | "processing" | "completed" | "abandoned" | "failed";

export interface Answer {
  question_id: string;
  value: string | number | boolean | string[];
  raw_text: string | null;
}

export interface TranscriptTurn {
  role: "agent" | "respondent";
  text: string;
  at?: string;
}

export interface SurveyResponse {
  id: string;
  survey_id: string;
  channel: Channel;
  status: ResponseStatus;
  respondent: { name?: string; email?: string; phone?: string };
  started_at: string;
  completed_at: string | null;
  answer_count: number;
  answers?: Answer[];
  transcript?: TranscriptTurn[];
  meta?: Record<string, unknown>;
  error?: string | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
}

export interface Distribution {
  label: string;
  count: number;
}

export interface QuestionStats {
  question_id: string;
  title: string;
  type: QuestionType;
  answered: number;
  skipped: number;
  distribution?: Distribution[];
  average?: number | null;
  median?: number;
  min?: number;
  max?: number;
  nps?: { score: number; promoters: number; passives: number; detractors: number };
  samples?: string[];
  note?: string;
}

export interface Analytics {
  summary: {
    started: number;
    completed: number;
    in_progress: number;
    completion_rate: number | null;
    median_duration_seconds: number | null;
  };
  channels: { channel: Channel; count: number }[];
  timeline: { date: string; count: number }[];
  questions: QuestionStats[];
}

export interface Insights {
  headline: string;
  summary: string;
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  key_findings: { title: string; detail: string }[];
  themes: { theme: string; prevalence: string; quote: string }[];
  recommendations: string[];
}

export interface Plan {
  id: PlanId;
  name: string;
  price_monthly: number | null;
  tagline: string;
  limits: Record<string, number | null>;
  features: string[];
  purchasable: boolean;
  highlights: string[];
}

export interface UsageMetric {
  used: number;
  limit: number | null;
}

export interface Billing {
  subscription: {
    plan: PlanId;
    status: string;
    current_period_start: string | null;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
    managed_by_stripe: boolean;
  };
  plan: Plan;
  usage: Record<"responses" | "ai_generations" | "voice_minutes" | "active_surveys" | "seats", UsageMetric> & {
    period_start: string;
  };
  plans: Plan[];
  features: Record<string, string>;
  stripe_enabled: boolean;
  can_manage: boolean;
}

export interface Member {
  id: string;
  role: Role;
  user: User;
  created_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  created_at: string;
  expires_at: string;
  accept_link?: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  key?: string;
}

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
  last_delivery_at: string | null;
  last_status: number | null;
  failure_count: number;
  secret?: string;
}

export interface Outreach {
  id: string;
  name: string;
  phone: string;
  status: "queued" | "calling" | "completed" | "failed";
  response_id: string | null;
  error: string | null;
  created_at: string;
}

export interface PublicSurvey {
  token: string;
  title: string;
  description: string;
  status: SurveyStatus;
  questions: Question[];
  modes: Mode[];
  welcome_message: string;
  closing_message: string;
  agent_name: string;
  collect: { name?: boolean; email?: boolean };
  show_branding: boolean;
  accepting_responses: boolean;
  organization: { name: string; branding: { logo_url?: string; primary_color?: string } };
}
