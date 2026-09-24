"""Response lifecycle: start, answer, complete, and post-completion side effects."""
from __future__ import annotations

import hmac
import logging

from flask import current_app
from sqlalchemy import func, select

from ..billing.entitlements import record_usage, require_feature, require_quota
from ..errors import APIError, Forbidden
from ..extensions import db
from ..models import (
    Answer,
    Channel,
    Organization,
    Question,
    Response,
    ResponseStatus,
    Survey,
    SurveyStatus,
)
from ..tasks import enqueue
from ..utils import new_token, sha256, utcnow
from .answers import AnswerError, format_answer, is_empty, normalize_answer

logger = logging.getLogger(__name__)

_MODE_FEATURE = {Channel.CHAT: "chat", Channel.VOICE: "voice", Channel.PHONE: "phone"}


def completed_count(survey_id: str) -> int:
    return db.session.scalar(
        select(func.count()).select_from(Response).where(
            Response.survey_id == survey_id, Response.status == ResponseStatus.COMPLETED.value
        )
    ) or 0


def assert_accepting(survey: Survey) -> None:
    if survey.status != SurveyStatus.PUBLISHED.value:
        raise APIError("This survey is not accepting responses", code="survey_closed", status=410)
    limit = (survey.settings or {}).get("response_limit")
    if limit and completed_count(survey.id) >= limit:
        raise APIError("This survey has reached its response limit", code="survey_closed", status=410)


def create_response(
    survey: Survey,
    channel: Channel,
    respondent: dict | None = None,
    outreach_id: str | None = None,
) -> tuple[Response, str]:
    """Start a response. Returns the row and the respondent's plaintext access token."""
    assert_accepting(survey)
    org = db.session.get(Organization, survey.org_id)
    modes = (survey.settings or {}).get("modes", ["form"])
    if channel in (Channel.FORM, Channel.CHAT, Channel.VOICE) and channel.value not in modes:
        raise APIError(f"{channel.value.title()} responses are not enabled for this survey", code="mode_disabled")
    if channel in _MODE_FEATURE:
        require_feature(org, _MODE_FEATURE[channel])
    require_quota(org, "responses")

    token = new_token(24)
    response = Response(
        survey_id=survey.id,
        org_id=survey.org_id,
        channel=channel.value,
        access_token_hash=sha256(token),
        respondent=respondent or {},
        outreach_id=outreach_id,
        transcript=[],
        meta={},
    )
    db.session.add(response)
    db.session.commit()
    return response, token


def token_matches(response: Response, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(response.access_token_hash, sha256(token))


def verify_access(response: Response, token: str | None) -> None:
    if not token_matches(response, token):
        raise Forbidden("Invalid response token")
    if response.status != ResponseStatus.IN_PROGRESS.value:
        raise APIError("This response has already been submitted", code="response_closed", status=409)


def save_answer(response: Response, question: Question, value, raw_text: str | None = None) -> Answer:
    normalized = normalize_answer(question, value)
    existing = next((a for a in response.answers if a.question_id == question.id), None)
    if existing:
        existing.value = normalized
        existing.raw_text = raw_text
        return existing
    answer = Answer(response_id=response.id, question_id=question.id, value=normalized, raw_text=raw_text)
    response.answers.append(answer)
    return answer


def save_form_answers(response: Response, answers: dict, *, complete: bool) -> dict[str, str]:
    """Validate and store form-mode answers. Returns field errors keyed by question id."""
    questions = {q.id: q for q in response.survey.active_questions}
    errors: dict[str, str] = {}
    for question_id, value in answers.items():
        question = questions.get(question_id)
        if question is None:
            continue
        if is_empty(value):
            existing = next((a for a in response.answers if a.question_id == question_id), None)
            if existing:
                response.answers.remove(existing)  # delete-orphan cascade removes the row
            continue
        try:
            save_answer(response, question, value)
        except AnswerError as exc:
            errors[question_id] = str(exc)

    if complete and not errors:
        answered = {a.question_id for a in response.answers}
        for question in questions.values():
            if question.required and question.id not in answered:
                errors[question.id] = "This question is required"
    if errors:
        db.session.rollback()
        return errors
    if complete:
        complete_response(response)
    else:
        db.session.commit()
    return {}


def complete_response(response: Response, *, declined: bool = False) -> None:
    if response.status == ResponseStatus.COMPLETED.value:
        return
    response.status = ResponseStatus.COMPLETED.value
    response.completed_at = utcnow()
    if declined:
        response.meta = {**(response.meta or {}), "declined": True}
    record_usage(response.org_id, "responses", 1, ref_id=response.id)
    survey = response.survey
    limit = (survey.settings or {}).get("response_limit")
    db.session.flush()
    if limit and completed_count(survey.id) >= limit:
        survey.status = SurveyStatus.CLOSED.value
        survey.closed_at = utcnow()
    db.session.commit()
    enqueue(on_response_completed, response.id)


def fail_response(response: Response, message: str) -> None:
    response.status = ResponseStatus.FAILED.value
    response.error = message[:2000]
    db.session.commit()


def response_payload(response: Response) -> dict:
    """Webhook/API representation with answers keyed by question."""
    questions = {q.id: q for q in response.survey.questions}
    return {
        **response.to_dict(),
        "survey": {"id": response.survey.id, "title": response.survey.title},
        "answers": [
            {
                "question_id": a.question_id,
                "question": questions[a.question_id].title if a.question_id in questions else None,
                "type": questions[a.question_id].type if a.question_id in questions else None,
                "value": a.value,
            }
            for a in response.answers
        ],
    }


def on_response_completed(response_id: str) -> None:
    """Fan out side effects after a response completes (runs in the background)."""
    from .email import render_email, send_email
    from .webhooks import dispatch_event

    response = db.session.get(Response, response_id)
    if response is None:
        return
    survey = response.survey
    org = db.session.get(Organization, survey.org_id)
    settings = survey.settings or {}

    dispatch_event(org.id, "response.completed", response_payload(response))

    recipients = settings.get("notify_emails") or []
    if recipients:
        questions = {q.id: q for q in survey.questions}
        lines = [
            f"{questions[a.question_id].title}: {format_answer(questions[a.question_id], a.value)}"
            for a in response.answers
            if a.question_id in questions
        ]
        url = f"{current_app.config['FRONTEND_URL']}/dashboard/surveys/{survey.id}/responses?response={response.id}"
        send_email(
            recipients,
            f"New response: {survey.title}",
            render_email(f"New {response.channel} response to “{survey.title}”", lines[:25], ("View response", url)),
        )
