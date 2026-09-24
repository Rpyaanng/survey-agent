"""Google Forms import.

Adapted from med-doc-flask's ``new_forms_functions``. Form structure comes
from the ``FB_PUBLIC_LOAD_DATA_`` JSON embedded in the public viewform page
and maps deterministically onto typed questions (no LLM needed). Import is
one-way: the resulting survey is fully native, and every response is
collected and stored by Survey Agent. Nothing is sent back to Google.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from ...errors import APIError
from ...models import QuestionType

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
}
_ALLOWED_HOSTS = {"docs.google.com", "forms.gle"}

# Google Forms item type codes -> our question types.
_TYPE_MAP = {
    0: QuestionType.SHORT_TEXT,
    1: QuestionType.LONG_TEXT,
    2: QuestionType.SINGLE_CHOICE,
    3: QuestionType.DROPDOWN,
    4: QuestionType.MULTIPLE_CHOICE,
    5: QuestionType.RATING,  # linear scale
    9: QuestionType.DATE,
    10: QuestionType.TIME,
}
_SKIP_TYPES = {6, 8, 11, 12}  # description, section header, image, video


def _normalize_url(url: str, last_segment: str) -> str:
    parts = urlsplit(url)
    if parts.hostname not in _ALLOWED_HOSTS:
        raise APIError("Please provide a docs.google.com/forms link", code="invalid_form_url")
    path = parts.path.rstrip("/")
    if parts.hostname == "docs.google.com":
        segments = path.split("/")
        if "forms" not in segments:
            raise APIError("Please provide a Google Forms link", code="invalid_form_url")
        if segments[-1] in {"viewform", "edit", "formResponse", "prefill"}:
            segments = segments[:-1]
        path = "/".join(segments) + f"/{last_segment}"
    return urlunsplit((parts.scheme or "https", parts.netloc, path, "", ""))


def _fetch_form_json(url: str) -> tuple[list, str]:
    view_url = _normalize_url(url, "viewform")
    try:
        resp = requests.get(view_url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise APIError("Couldn't load that Google Form. Is it public?", code="form_unreachable") from exc
    final_url = resp.url  # forms.gle short links redirect to the real form
    soup = BeautifulSoup(resp.text, "html.parser")
    for script in soup.find_all("script"):
        if script.string and "FB_PUBLIC_LOAD_DATA_" in script.string:
            match = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(.*?);?\s*$", script.string.strip(), re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).rstrip(";")), final_url
                except json.JSONDecodeError as exc:
                    raise APIError("Couldn't parse that Google Form", code="form_unparseable") from exc
    raise APIError(
        "That form requires sign-in or isn't a Google Form. Make it public and try again.",
        code="form_unparseable",
    )


def parse_form(data: list) -> dict[str, Any]:
    """Turn FB_PUBLIC_LOAD_DATA_ into {title, description, questions[]} (QuestionIn-shaped dicts)."""
    try:
        form = data[1]
        items = form[1] or []
    except (IndexError, TypeError) as exc:
        raise APIError("Unexpected Google Form structure", code="form_unparseable") from exc

    title = (form[8] if len(form) > 8 and form[8] else None) or (data[3] if len(data) > 3 else None) or "Imported form"
    description = form[0] if form and isinstance(form[0], str) else ""
    questions: list[dict[str, Any]] = []

    try:
        if form[10][6] in (2, 3):  # form collects respondent emails
            questions.append({
                "type": QuestionType.EMAIL.value, "title": "Email address", "required": True,
            })
    except (IndexError, TypeError):
        pass

    for item in items:
        if not isinstance(item, list) or len(item) < 4:
            continue
        type_code = item[3]
        if type_code in _SKIP_TYPES or not item[1]:
            continue
        if not isinstance(item[4] if len(item) > 4 else None, list) or not item[4]:
            continue
        qtype = _TYPE_MAP.get(type_code)
        if qtype is None:  # grids and file uploads aren't supported conversationally
            logger.info("Skipping unsupported Google Forms item type %s", type_code)
            continue
        details = item[4][0]
        raw_options = details[1] if len(details) > 1 and details[1] else []
        option_labels = [o[0] for o in raw_options if isinstance(o, list) and o and o[0] not in (None, "")]
        allow_other = any(isinstance(o, list) and len(o) > 4 and o[4] == 1 for o in raw_options)
        options: dict[str, Any] = {}
        if qtype.has_choices:
            if len(option_labels) < 2:
                qtype = QuestionType.SHORT_TEXT
            else:
                options = {"choices": option_labels, "allow_other": allow_other}
        elif qtype == QuestionType.RATING:
            numbers = [int(x) for x in option_labels if str(x).lstrip("-").isdigit()]
            labels = details[3] if len(details) > 3 and isinstance(details[3], list) else ["", ""]
            options = {
                "min": min(numbers) if numbers else 1,
                "max": max(numbers) if numbers else 5,
                "min_label": (labels[0] or "") if labels else "",
                "max_label": (labels[1] or "") if len(labels) > 1 else "",
            }
        questions.append({
            "type": qtype.value,
            "title": item[1],
            "description": item[2] or "",
            "required": bool(len(details) > 2 and details[2] == 1),
            "options": options,
        })
    return {"title": title, "description": description or "", "questions": questions}


def import_google_form(url: str) -> dict[str, Any]:
    """Fetch a public Google Form and return its title, description and questions."""
    data, final_url = _fetch_form_json(url)
    parsed = parse_form(data)
    if not parsed["questions"]:
        raise APIError("No supported questions were found in that form", code="form_empty")
    parsed["url"] = _normalize_url(final_url, "viewform")  # kept for provenance only
    return parsed
