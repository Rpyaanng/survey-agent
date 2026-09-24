"""Survey authoring: creation, question editing, publishing and duplication."""
from __future__ import annotations

from sqlalchemy import exists, select

from ..billing.entitlements import has_feature, require_active_survey_slot
from ..errors import APIError
from ..extensions import db
from ..models import Answer, Organization, Question, Survey, SurveyStatus
from ..schemas import QuestionIn, SurveySettings
from ..utils import utcnow


def default_settings(**overrides) -> dict:
    return SurveySettings(**overrides).model_dump(mode="json")


def merged_settings(survey: Survey) -> dict:
    """Stored settings layered over defaults, so older surveys pick up new keys."""
    return {**default_settings(), **(survey.settings or {})}


def create_survey(
    org: Organization,
    *,
    title: str,
    description: str = "",
    questions: list[QuestionIn] | None = None,
    settings: SurveySettings | dict | None = None,
    source: dict | None = None,
    created_by_id: str | None = None,
) -> Survey:
    if isinstance(settings, SurveySettings):
        settings_dict = settings.model_dump(mode="json")
    else:
        settings_dict = default_settings(**(settings or {}))
    survey = Survey(
        org_id=org.id,
        title=title,
        description=description,
        settings=settings_dict,
        source=source or {"type": "manual"},
        created_by_id=created_by_id,
    )
    db.session.add(survey)
    db.session.flush()
    for position, q in enumerate(questions or []):
        survey.questions.append(_new_question(q, position))
    db.session.commit()
    return survey


def _new_question(q: QuestionIn, position: int) -> Question:
    return Question(
        position=position,
        type=q.type.value,
        title=q.title,
        description=q.description,
        required=q.required,
        options=q.options_dict(),
    )


def _has_answers(question_id: str) -> bool:
    return bool(db.session.scalar(select(exists().where(Answer.question_id == question_id))))


def replace_questions(survey: Survey, incoming: list[QuestionIn]) -> Survey:
    """Apply the builder's full question list: update, insert, reorder, remove.

    Removed questions that already have answers are archived rather than
    deleted, so historical responses and exports keep their data.
    """
    existing = {q.id: q for q in survey.questions if not q.archived}
    seen: set[str] = set()
    for position, q in enumerate(incoming):
        current = existing.get(q.id) if q.id else None
        if current is None:
            survey.questions.append(_new_question(q, position))
            continue
        seen.add(current.id)
        type_changed = current.type != q.type.value
        if type_changed and _has_answers(current.id):
            # Changing the type would invalidate stored answers: archive and replace.
            current.archived = True
            survey.questions.append(_new_question(q, position))
            continue
        current.position = position
        current.type = q.type.value
        current.title = q.title
        current.description = q.description
        current.required = q.required
        current.options = q.options_dict()

    for question_id, question in existing.items():
        if question_id in seen:
            continue
        if _has_answers(question_id):
            question.archived = True
        else:
            survey.questions.remove(question)
    survey.updated_at = utcnow()
    db.session.commit()
    db.session.refresh(survey)
    return survey


def publish(survey: Survey, org: Organization) -> Survey:
    if survey.status == SurveyStatus.PUBLISHED.value:
        return survey
    if not survey.active_questions:
        raise APIError("Add at least one question before publishing", code="no_questions")
    require_active_survey_slot(org)
    modes = merged_settings(survey)["modes"]
    if "voice" in modes and not has_feature(org, "voice"):
        survey.settings = {**merged_settings(survey), "modes": [m for m in modes if m != "voice"] or ["form"]}
    survey.status = SurveyStatus.PUBLISHED.value
    survey.published_at = survey.published_at or utcnow()
    survey.closed_at = None
    db.session.commit()
    return survey


def close(survey: Survey) -> Survey:
    survey.status = SurveyStatus.CLOSED.value
    survey.closed_at = utcnow()
    db.session.commit()
    return survey


def duplicate(survey: Survey, created_by_id: str | None) -> Survey:
    org = db.session.get(Organization, survey.org_id)
    questions = [
        QuestionIn(
            type=q.type, title=q.title, description=q.description, required=q.required,
            options=q.options or {},
        )
        for q in survey.active_questions
    ]
    return create_survey(
        org,
        title=f"{survey.title} (copy)"[:200],
        description=survey.description,
        questions=questions,
        settings=merged_settings(survey),
        source=survey.source,
        created_by_id=created_by_id,
    )


def public_view(survey: Survey) -> dict:
    """What respondents see. Never includes internal IDs beyond question ids."""
    org = db.session.get(Organization, survey.org_id)
    settings = merged_settings(survey)
    show_branding = settings.get("show_branding", True) or not has_feature(org, "remove_branding")
    modes = [m for m in settings["modes"] if m != "voice" or has_feature(org, "voice")]
    return {
        "token": survey.public_token,
        "title": survey.title,
        "description": survey.description,
        "status": survey.status,
        "questions": [q.to_dict() for q in survey.active_questions],
        "modes": modes,
        "welcome_message": settings.get("welcome_message", ""),
        "closing_message": settings.get("closing_message", ""),
        "agent_name": (settings.get("agent") or {}).get("name", "Ava"),
        "collect": settings.get("collect", {}),
        "show_branding": show_branding,
        "organization": {"name": org.name, "branding": org.branding or {}},
    }
