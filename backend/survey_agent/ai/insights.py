"""AI-written executive summary of a survey's results."""
from __future__ import annotations

import json
from typing import Any

from ..models import QuestionType, Survey
from .provider import get_provider, load_prompt

MAX_TEXT_CHARS = 120_000

INSIGHTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "detail": {"type": "string"}},
                "required": ["title", "detail"],
                "additionalProperties": False,
            },
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "prevalence": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["theme", "prevalence", "quote"],
                "additionalProperties": False,
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "summary", "sentiment", "key_findings", "themes", "recommendations"],
    "additionalProperties": False,
}

_TEXT_TYPES = {QuestionType.SHORT_TEXT.value, QuestionType.LONG_TEXT.value}


def generate_insights(survey: Survey, analytics: dict[str, Any], text_answers: dict[str, list[str]]) -> dict[str, Any]:
    aggregates = {
        "summary": analytics["summary"],
        "channels": analytics["channels"],
        "questions": [
            {k: v for k, v in q.items() if k != "samples"} for q in analytics["questions"] if q["type"] not in _TEXT_TYPES
        ],
    }
    titles = {q.id: q.title for q in survey.active_questions}
    blocks, used = [], 0
    for question_id, answers in text_answers.items():
        block = f"### {titles.get(question_id, question_id)}\n" + "\n".join(f"- {a}" for a in answers)
        if used + len(block) > MAX_TEXT_CHARS:
            blocks.append(f"### {titles.get(question_id, question_id)}\n(truncated: sample limit reached)")
            break
        blocks.append(block)
        used += len(block)

    return get_provider().generate_json(
        task="insights",
        system=load_prompt(
            "insights.md",
            SURVEY_TITLE=survey.title,
            SURVEY_DESCRIPTION=survey.description or "",
            AGGREGATES=json.dumps(aggregates, indent=1),
            TEXT_ANSWERS="\n\n".join(blocks) or "(no open-text questions)",
        ),
        messages=[{"role": "user", "content": "Write the analysis."}],
        schema=INSIGHTS_SCHEMA,
        effort="high",
        hint={"analytics": analytics},
    )
