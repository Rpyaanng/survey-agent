"""AI survey generation from a plain-language brief or from an uploaded form document."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from ..models import QuestionType
from ..schemas import QuestionIn
from .provider import AIError, get_provider, load_prompt

logger = logging.getLogger(__name__)

MAX_DOCUMENT_CHARS = 400_000  # ~100k tokens; well inside the model's context window

SURVEY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "welcome_message": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": [t.value for t in QuestionType]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "required": {"type": "boolean"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "scale_min": {"type": "integer"},
                    "scale_max": {"type": "integer"},
                    "min_label": {"type": "string"},
                    "max_label": {"type": "string"},
                },
                "required": [
                    "type", "title", "description", "required", "choices",
                    "scale_min", "scale_max", "min_label", "max_label",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "description", "welcome_message", "questions"],
    "additionalProperties": False,
}


def _to_questions(raw_questions: list[dict[str, Any]]) -> list[QuestionIn]:
    """Validate model output through the same schema the API uses; drop anything invalid."""
    questions: list[QuestionIn] = []
    for raw in raw_questions:
        qtype = raw.get("type")
        options: dict[str, Any] = {"choices": raw.get("choices") or []}
        if qtype == QuestionType.RATING.value:
            options.update(min=raw.get("scale_min") or 1, max=raw.get("scale_max") or 5)
        if qtype in (QuestionType.RATING.value, QuestionType.NPS.value):
            options.update(min_label=raw.get("min_label", ""), max_label=raw.get("max_label", ""))
        try:
            questions.append(
                QuestionIn(
                    type=qtype,
                    title=raw.get("title", ""),
                    description=raw.get("description", ""),
                    required=bool(raw.get("required")),
                    options=options,
                )
            )
        except ValidationError as exc:
            logger.info("Dropping invalid generated question %r: %s", raw.get("title"), exc.errors()[0]["msg"])
    return questions


def _finish(result: dict[str, Any]) -> dict[str, Any]:
    questions = _to_questions(result.get("questions", []))
    if not questions:
        raise AIError("The AI couldn't produce any usable questions. Try rephrasing your request.")
    return {
        "title": (result.get("title") or "Untitled survey")[:200],
        "description": result.get("description", "")[:5000],
        "welcome_message": result.get("welcome_message", "")[:2000],
        "questions": questions,
    }


def generate_from_prompt(prompt: str, question_count: int = 8) -> dict[str, Any]:
    result = get_provider().generate_json(
        task="generate_survey",
        system=load_prompt("survey_builder.md"),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Design a survey with about {question_count} questions for the following brief.\n\n"
                    f"<brief>\n{prompt}\n</brief>"
                ),
            }
        ],
        schema=SURVEY_SCHEMA,
        effort="high",
        hint={"prompt": prompt, "question_count": question_count},
    )
    return _finish(result)


def generate_from_document(text: str, filename: str, field_names: list[str] | None = None) -> dict[str, Any]:
    if len(text) > MAX_DOCUMENT_CHARS:
        raise AIError("This document is too long to import. Split it into smaller forms.")
    hints = ""
    if field_names:
        hints = "The PDF also defines these fillable fields, which must all be covered:\n" + "\n".join(
            f"- {name}" for name in field_names[:500]
        )
    result = get_provider().generate_json(
        task="import_document",
        system=load_prompt("survey_builder.md"),
        messages=[
            {
                "role": "user",
                "content": load_prompt("document_import.md", DOCUMENT=text, FILENAME=filename, FIELD_HINTS=hints),
            }
        ],
        schema=SURVEY_SCHEMA,
        effort="high",
        max_tokens=32000,
        hint={"text": text, "filename": filename, "field_names": field_names or []},
    )
    return _finish(result)
