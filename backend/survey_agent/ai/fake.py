"""Deterministic, rule-based stand-in for the LLM.

It lets the app run end to end without an API key (local development, demos,
CI) and makes tests reproducible. It follows the same JSON schemas as the real
provider, so callers can't tell the difference structurally.
"""
from __future__ import annotations

import re
from typing import Any

from ..models import Question, QuestionType
from ..services.answers import AnswerError, normalize_answer

_SKIP = {"skip", "pass", "prefer not to say", "i don't know", "i dont know", "no comment", "n/a"}
_STOP = {"stop", "quit", "exit", "end survey", "i want to stop"}


def _question(data: dict[str, Any]) -> Question:
    return Question(id=data["id"], type=data["type"], title=data["title"], options=data.get("options") or {})


def _coerce(data: dict[str, Any], message: str) -> str:
    qtype = QuestionType(data["type"])
    text = message.strip()
    lowered = text.lower()
    choices = (data.get("options") or {}).get("choices", [])
    if qtype.has_choices:
        hits = [c for c in choices if c.lower() in lowered]
        if qtype == QuestionType.MULTIPLE_CHOICE and hits:
            return " | ".join(hits)
        if hits:
            return max(hits, key=len)
    if qtype in (QuestionType.RATING, QuestionType.NPS, QuestionType.NUMBER):
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if match:
            return match.group()
    if qtype == QuestionType.YES_NO:
        if re.search(r"\b(yes|yeah|yep|sure|definitely)\b", lowered):
            return "yes"
        if re.search(r"\b(no|nope|never|not really)\b", lowered):
            return "no"
    return text


def _ask(data: dict[str, Any]) -> str:
    qtype = QuestionType(data["type"])
    opts = data.get("options") or {}
    question = data["title"].rstrip()
    if qtype.has_choices:
        choices = opts.get("choices", [])
        joined = ", ".join(choices[:-1]) + f", or {choices[-1]}" if len(choices) > 1 else "".join(choices)
        hint = "Pick any that apply: " if qtype == QuestionType.MULTIPLE_CHOICE else "Your options are "
        return f"{question} {hint}{joined}."
    if qtype in (QuestionType.RATING, QuestionType.NPS):
        return f"{question} (on a scale from {opts.get('min', 0)} to {opts.get('max', 10)})"
    if qtype == QuestionType.YES_NO:
        return f"{question} (yes or no)"
    return question


class FakeProvider:
    name = "fake"

    def generate_json(self, *, task, system, messages, schema, effort="medium", max_tokens=16000, hint=None):
        handler = getattr(self, f"_{task}", None)
        if handler is None:
            raise NotImplementedError(f"FakeProvider has no handler for task '{task}'")
        return handler(hint or {})

    # ------------------------------------------------------------- interview
    def _interview_turn(self, hint: dict[str, Any]) -> dict[str, Any]:
        questions = hint["questions"]
        done = set(hint.get("answered_ids", [])) | set(hint.get("skipped_ids", []))
        pending = [q for q in questions if q["id"] not in done]
        message = (hint.get("message") or "").strip()
        settings = hint.get("settings") or {}
        closing = settings.get("closing_message") or "Thanks for your time!"
        answers: list[dict[str, str]] = []
        skipped: list[str] = []

        if not message:
            agent = (settings.get("agent") or {}).get("name") or "Ava"
            greeting = settings.get("welcome_message") or f"Hi, I'm {agent}! Thanks for taking a few minutes to chat."
            if not pending:
                return {"answers": [], "skipped_question_ids": [], "reply": closing, "status": "completed"}
            return {
                "answers": [],
                "skipped_question_ids": [],
                "reply": f"{greeting} {_ask(pending[0])}",
                "status": "in_progress",
            }

        if message.lower().strip(".! ") in _STOP:
            return {"answers": [], "skipped_question_ids": [], "reply": closing, "status": "respondent_declined"}

        if pending:
            current = pending[0]
            if message.lower().strip(".! ") in _SKIP:
                skipped.append(current["id"])
                pending = pending[1:]
                prefix = "No problem, we'll skip that one. "
            else:
                value = _coerce(current, message)
                try:
                    normalize_answer(_question(current), value)
                except AnswerError as exc:
                    return {
                        "answers": [],
                        "skipped_question_ids": [],
                        "reply": f"Sorry, I didn't quite get that ({exc}). {_ask(current)}",
                        "status": "in_progress",
                    }
                answers.append({"question_id": current["id"], "value": value, "raw_text": message})
                pending = pending[1:]
                prefix = "Thanks! "
        else:
            prefix = ""

        if not pending:
            return {"answers": answers, "skipped_question_ids": skipped, "reply": closing, "status": "completed"}
        return {
            "answers": answers,
            "skipped_question_ids": skipped,
            "reply": prefix + _ask(pending[0]),
            "status": "in_progress",
        }

    # ------------------------------------------------------------ extraction
    def _extract_answers(self, hint: dict[str, Any]) -> dict[str, Any]:
        questions = hint["questions"]
        transcript = hint["transcript"]
        answers: dict[str, dict[str, str]] = {}
        current = None
        for turn in transcript:
            text = turn.get("text", "")
            if turn.get("role") == "agent":
                current = next((q for q in questions if q["title"].lower().rstrip("?") in text.lower()), current)
            elif current is not None:
                value = _coerce(current, text)
                try:
                    normalize_answer(_question(current), value)
                except AnswerError:
                    continue
                answers[current["id"]] = {"question_id": current["id"], "value": value, "raw_text": text}
        return {"answers": list(answers.values())}

    # --------------------------------------------------------------- builder
    def _generate_survey(self, hint: dict[str, Any]) -> dict[str, Any]:
        topic = re.sub(r"\s+", " ", hint.get("prompt", "your experience")).strip().rstrip(".")
        short = topic[:60]
        bank = [
            {"type": "rating", "title": f"Overall, how satisfied are you with {short}?", "scale_min": 1, "scale_max": 5,
             "min_label": "Very dissatisfied", "max_label": "Very satisfied"},
            {"type": "single_choice", "title": "How often do you engage with it?",
             "choices": ["Daily", "Weekly", "Monthly", "Rarely"]},
            {"type": "multiple_choice", "title": "Which aspects matter most to you?",
             "choices": ["Quality", "Price", "Speed", "Support", "Other"]},
            {"type": "long_text", "title": "What is the one thing we could improve?"},
            {"type": "nps", "title": "How likely are you to recommend it to a friend or colleague?"},
            {"type": "yes_no", "title": "Would you like us to follow up with you?"},
            {"type": "short_text", "title": "What is your role or occupation?"},
            {"type": "long_text", "title": "Is there anything else you'd like to share?"},
        ]
        count = max(3, min(int(hint.get("question_count", 8)), len(bank)))
        questions = []
        for item in bank[:count]:
            questions.append({
                "type": item["type"], "title": item["title"], "description": "", "required": item["type"] != "long_text",
                "choices": item.get("choices", []), "scale_min": item.get("scale_min", 0),
                "scale_max": item.get("scale_max", 0), "min_label": item.get("min_label", ""),
                "max_label": item.get("max_label", ""),
            })
        return {
            "title": f"Survey: {short[:1].upper()}{short[1:]}",
            "description": f"Help us understand {short}. It takes about three minutes.",
            "welcome_message": "Thanks for joining! This will only take a few minutes.",
            "questions": questions,
        }

    def _import_document(self, hint: dict[str, Any]) -> dict[str, Any]:
        lines = [ln.strip() for ln in hint.get("text", "").splitlines()]
        prompts = [ln.rstrip(":_ ").strip() for ln in lines if ln.endswith((":", "?")) and 3 <= len(ln) <= 200]
        prompts.extend(name.replace("_", " ") for name in hint.get("field_names", []))
        seen: list[str] = []
        for prompt in prompts:
            if prompt and prompt.lower() not in {s.lower() for s in seen}:
                seen.append(prompt)
        if not seen:
            seen = ["Please share the information requested in this form"]
        filename = hint.get("filename") or "form"
        return {
            "title": re.sub(r"\.pdf$", "", filename, flags=re.I).replace("_", " ").strip() or "Imported form",
            "description": "Imported from an uploaded document.",
            "welcome_message": "Thanks for filling this out with me.",
            "questions": [
                {"type": "long_text" if len(p) > 80 else "short_text", "title": p, "description": "", "required": False,
                 "choices": [], "scale_min": 0, "scale_max": 0, "min_label": "", "max_label": ""}
                for p in seen[:60]
            ],
        }

    # -------------------------------------------------------------- insights
    def _insights(self, hint: dict[str, Any]) -> dict[str, Any]:
        analytics = hint.get("analytics", {})
        summary = analytics.get("summary", {})
        completed = summary.get("completed", 0)
        findings = []
        for q in analytics.get("questions", []):
            if q.get("nps"):
                findings.append({"title": "Net Promoter Score", "detail": f"NPS is {q['nps']['score']} for '{q['title']}'."})
            elif q.get("average") is not None:
                findings.append({"title": q["title"], "detail": f"Average score {q['average']}."})
            elif q.get("distribution"):
                top = max(q["distribution"], key=lambda d: d["count"])
                findings.append({"title": q["title"], "detail": f"Most common answer: {top['label']} ({top['count']})."})
        return {
            "headline": f"{completed} completed responses analysed",
            "summary": f"This offline summary was generated without an AI model from {completed} completed responses. "
            "Set ANTHROPIC_API_KEY for full AI insights.",
            "sentiment": "neutral",
            "key_findings": findings[:6],
            "themes": [],
            "recommendations": ["Collect more responses to strengthen conclusions."] if completed < 30 else [],
        }
