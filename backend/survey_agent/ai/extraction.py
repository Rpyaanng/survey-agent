"""Extract structured answers from a finished voice or phone interview transcript."""
from __future__ import annotations

from typing import Any

from ..models import Survey
from .common import describe_questions
from .provider import get_provider, load_prompt


def extract_answers(survey: Survey, transcript: list[dict[str, str]]) -> list[dict[str, Any]]:
    questions = survey.active_questions
    if not questions or not transcript:
        return []
    ids = [q.id for q in questions]
    schema = {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string", "enum": ids},
                        "value": {"type": "string"},
                        "raw_text": {"type": "string"},
                    },
                    "required": ["question_id", "value", "raw_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    }
    rendered = "\n".join(
        f"{'Agent' if turn['role'] == 'agent' else 'Respondent'}: {turn['text']}" for turn in transcript
    )
    result = get_provider().generate_json(
        task="extract_answers",
        system=load_prompt("extract_answers.md", SURVEY_TITLE=survey.title, QUESTIONS=describe_questions(questions)),
        messages=[{"role": "user", "content": f"<transcript>\n{rendered}\n</transcript>"}],
        schema=schema,
        effort="medium",
        hint={"questions": [q.to_dict() for q in questions], "transcript": transcript},
    )
    return result.get("answers", [])
