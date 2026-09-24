"""Answer normalization.

Every answer, whether typed into a form, extracted by the AI interviewer, or
pulled from a phone transcript, goes through ``normalize_answer`` so stored
values always match the question type. That keeps analytics and exports
reliable no matter which channel produced the answer.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..models import Question, QuestionType

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()\-.]{7,20}$")
_YES = {"yes", "y", "true", "yeah", "yep", "sure", "correct", "1", "absolutely", "definitely"}
_NO = {"no", "n", "false", "nope", "nah", "0", "not really", "never"}
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d %B %Y", "%Y/%m/%d")
_TIME_FORMATS = ("%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H:%M:%S")
MAX_TEXT = 10_000


class AnswerError(ValueError):
    pass


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or (isinstance(value, str) and not value.strip())


def _match_choice(value: str, choices: list[str]) -> str | None:
    needle = value.strip().lower()
    for choice in choices:
        if choice.lower() == needle:
            return choice
    return None


def normalize_answer(question: Question, value: Any) -> Any:
    """Return the canonical value for ``question`` or raise ``AnswerError``."""
    if is_empty(value):
        raise AnswerError("Answer is empty")

    qtype = question.qtype
    opts = question.options or {}
    choices: list[str] = opts.get("choices", [])

    if qtype in (QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT):
        text = str(value).strip()
        return text[:MAX_TEXT]

    if qtype in (QuestionType.SINGLE_CHOICE, QuestionType.DROPDOWN):
        if isinstance(value, list):
            if len(value) != 1:
                raise AnswerError("Choose exactly one option")
            value = value[0]
        match = _match_choice(str(value), choices)
        if match:
            return match
        if opts.get("allow_other"):
            return str(value).strip()[:500]
        raise AnswerError(f"'{value}' is not one of the available options")

    if qtype == QuestionType.MULTIPLE_CHOICE:
        items = value if isinstance(value, list) else _split_selections(str(value), choices)
        result: list[str] = []
        for item in items:
            match = _match_choice(str(item), choices)
            if match is None:
                if not opts.get("allow_other"):
                    raise AnswerError(f"'{item}' is not one of the available options")
                match = str(item).strip()[:500]
            if match not in result:
                result.append(match)
        if not result:
            raise AnswerError("Choose at least one option")
        return result

    if qtype in (QuestionType.RATING, QuestionType.NPS):
        lo = opts.get("min", 0 if qtype == QuestionType.NPS else 1)
        hi = opts.get("max", 10 if qtype == QuestionType.NPS else 5)
        number = _to_number(value)
        if number is None or number != int(number):
            raise AnswerError(f"Answer must be a whole number between {lo} and {hi}")
        number = int(number)
        if not lo <= number <= hi:
            raise AnswerError(f"Answer must be between {lo} and {hi}")
        return number

    if qtype == QuestionType.YES_NO:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower().rstrip(".!")
        if text in _YES:
            return True
        if text in _NO:
            return False
        raise AnswerError("Answer must be yes or no")

    if qtype == QuestionType.NUMBER:
        number = _to_number(value)
        if number is None:
            raise AnswerError("Answer must be a number")
        return int(number) if number == int(number) else number

    if qtype == QuestionType.EMAIL:
        text = str(value).strip()
        if not _EMAIL_RE.match(text):
            raise AnswerError("Answer must be a valid email address")
        return text.lower()

    if qtype == QuestionType.PHONE:
        text = str(value).strip()
        if not _PHONE_RE.match(text):
            raise AnswerError("Answer must be a valid phone number")
        return text

    if qtype == QuestionType.DATE:
        text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", str(value).strip())
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        raise AnswerError("Answer must be a date (YYYY-MM-DD)")

    if qtype == QuestionType.TIME:
        text = str(value).strip().upper().replace(".", "")
        for fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(text, fmt).strftime("%H:%M")
            except ValueError:
                continue
        raise AnswerError("Answer must be a time (HH:MM)")

    raise AnswerError(f"Unsupported question type {qtype}")


def _split_selections(text: str, choices: list[str]) -> list[str]:
    # Options can contain commas ("Yes, weekly"), so prefer exact matches and explicit separators.
    if _match_choice(text, choices):
        return [text]
    for separator in ("|", "__", ";"):
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip()]
    return [part for part in re.split(r"\s*,\s*", text) if part]


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def format_answer(question: Question, value: Any) -> str:
    """Human-readable rendering, used in exports, emails and the AI prompts."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)
