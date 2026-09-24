"""AI chat interviewer.

The model is stateless: each turn, the database state (questions, answers
captured so far, skips, validation feedback) is rendered into the system
prompt. The model returns structured JSON with its reply plus any answers it
heard. Answers are normalized server-side before storage; if one fails
validation, the failure is fed back on the next turn so the model re-asks.
"""
from __future__ import annotations

import logging
from typing import Any

from ..models import Organization, Response, ResponseStatus
from ..extensions import db
from ..services.answers import AnswerError, format_answer
from ..services.responses import complete_response, save_answer
from ..utils import iso, utcnow
from .common import TONE_GUIDE, describe_questions
from .provider import get_provider, load_prompt

logger = logging.getLogger(__name__)

MAX_TURNS = 80
OPENING_CUE = "[The respondent has opened the survey. Greet them briefly and ask the first question.]"


def _turn_schema(question_ids: list[str]) -> dict[str, Any]:
    qid: dict[str, Any] = {"type": "string"}
    if question_ids:
        qid["enum"] = question_ids
    return {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": qid,
                        "value": {"type": "string"},
                        "raw_text": {"type": "string"},
                    },
                    "required": ["question_id", "value", "raw_text"],
                    "additionalProperties": False,
                },
            },
            "skipped_question_ids": {"type": "array", "items": qid},
            "reply": {"type": "string"},
            "status": {"type": "string", "enum": ["in_progress", "completed", "respondent_declined"]},
        },
        "required": ["answers", "skipped_question_ids", "reply", "status"],
        "additionalProperties": False,
    }


def _progress_block(response: Response, skipped: set[str], feedback: list[str]) -> str:
    answered = response.answers_by_question()
    lines = []
    for question in response.survey.active_questions:
        if question.id in answered:
            lines.append(f"- {question.id}: ANSWERED -> {format_answer(question, answered[question.id].value)}")
        elif question.id in skipped:
            lines.append(f"- {question.id}: SKIPPED by respondent")
        else:
            lines.append(f"- {question.id}: not yet answered")
    if feedback:
        lines.append("\nValidation problems from the last turn (re-ask these politely):")
        lines.extend(f"- {item}" for item in feedback)
    return "\n".join(lines) or "No questions."


def build_system_prompt(response: Response, skipped: set[str], feedback: list[str]) -> str:
    survey = response.survey
    settings = survey.settings or {}
    agent = settings.get("agent") or {}
    org = db.session.get(Organization, survey.org_id)
    instructions = agent.get("instructions", "").strip()
    return load_prompt(
        "interviewer_system.md",
        AGENT_NAME=agent.get("name") or "Ava",
        ORG_NAME=org.name if org else "the survey owner",
        SURVEY_TITLE=survey.title,
        SURVEY_DESCRIPTION=survey.description or "(no description)",
        WELCOME_MESSAGE=settings.get("welcome_message") or "(none: write a short, friendly greeting)",
        CLOSING_MESSAGE=settings.get("closing_message") or "Thank the respondent for their time.",
        TONE=TONE_GUIDE.get(agent.get("tone", "friendly"), TONE_GUIDE["friendly"]),
        CUSTOM_INSTRUCTIONS=f"Additional instructions from the survey owner: {instructions}" if instructions else "",
        QUESTIONS=describe_questions(survey.active_questions),
        PROGRESS=_progress_block(response, skipped, feedback),
    )


def _to_messages(transcript: list[dict]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "user", "content": OPENING_CUE}]
    for entry in transcript:
        role = "assistant" if entry.get("role") == "agent" else "user"
        messages.append({"role": role, "content": entry.get("text", "")})
    return messages


def progress(response: Response) -> dict[str, int]:
    total = len(response.survey.active_questions)
    return {"answered": len(response.answers), "total": total}


def run_chat_turn(response: Response, message: str | None) -> dict[str, Any]:
    """Advance the interview by one turn and return the agent's reply."""
    transcript = list(response.transcript or [])
    meta = dict(response.meta or {})

    # Re-opening the page: replay the last agent message instead of calling the model.
    if not message and transcript:
        last_agent = next((e["text"] for e in reversed(transcript) if e.get("role") == "agent"), "")
        return {"reply": last_agent, "completed": False, "progress": progress(response), "transcript": transcript}

    if message:
        transcript.append({"role": "respondent", "text": message, "at": iso(utcnow())})

    skipped = set(meta.get("skipped", []))
    feedback = list(meta.get("_feedback", []))
    questions = response.survey.active_questions
    question_ids = [q.id for q in questions]

    result = get_provider().generate_json(
        task="interview_turn",
        system=build_system_prompt(response, skipped, feedback),
        messages=_to_messages(transcript),
        schema=_turn_schema(question_ids),
        effort="low",  # latency matters in live chat; the task is well-specified
        max_tokens=8000,
        hint={
            "questions": [q.to_dict() for q in questions],
            "answered_ids": [a.question_id for a in response.answers],
            "skipped_ids": sorted(skipped),
            "message": message,
            "settings": response.survey.settings or {},
        },
    )

    by_id = {q.id: q for q in questions}
    new_feedback: list[str] = []
    for item in result.get("answers", []):
        question = by_id.get(item.get("question_id"))
        if question is None:
            continue
        try:
            save_answer(response, question, item.get("value"), raw_text=(item.get("raw_text") or None))
            skipped.discard(question.id)
        except AnswerError as exc:
            new_feedback.append(f"{question.id}: the answer '{item.get('value')}' was rejected ({exc})")

    answered_ids = {a.question_id for a in response.answers}
    for qid in result.get("skipped_question_ids", []):
        if qid in by_id and qid not in answered_ids:
            skipped.add(qid)

    reply = (result.get("reply") or "").strip() or "Sorry, could you say that again?"
    transcript.append({"role": "agent", "text": reply, "at": iso(utcnow())})

    meta["skipped"] = sorted(skipped)
    meta["_feedback"] = new_feedback
    meta["turns"] = int(meta.get("turns", 0)) + 1
    response.transcript = transcript
    response.meta = meta

    status = result.get("status", "in_progress")
    done = (
        status == "respondent_declined"
        or (status == "completed" and not new_feedback)
        or meta["turns"] >= MAX_TURNS
    )
    if done:
        complete_response(response, declined=status == "respondent_declined")
    else:
        db.session.commit()

    return {
        "reply": reply,
        "completed": response.status == ResponseStatus.COMPLETED.value,
        "progress": progress(response),
        "transcript": transcript,
    }
