"""Survey authoring, AI generation/import, analytics and phone outreach."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError
from sqlalchemy import func, or_, select

from ..ai.builder import generate_from_document, generate_from_prompt
from ..ai.insights import generate_insights
from ..ai.provider import AIError
from ..auth import actor_id, org_required
from ..billing.entitlements import record_usage, require_feature, require_quota
from ..errors import APIError
from ..extensions import db, limiter
from ..models import Outreach, QuestionType, Response, ResponseStatus, Role, Survey
from ..schemas import (
    GenerateSurveyIn,
    ImportGoogleFormIn,
    OutreachIn,
    QuestionIn,
    QuestionsReplaceIn,
    SurveyCreateIn,
    SurveyUpdateIn,
)
from ..services import surveys as survey_service
from ..services.analytics import survey_analytics
from ..services.importers.google_forms import import_google_form
from ..services.importers.pdf import extract_pdf
from ..services.voice import queue_outreach
from ..services.webhooks import dispatch_event
from .common import get_survey, paginate, parse

bp = Blueprint("surveys", __name__, url_prefix="/api/v1/surveys")


def _with_stats(survey: Survey) -> dict:
    counts = dict(
        db.session.execute(
            select(Response.status, func.count()).where(Response.survey_id == survey.id).group_by(Response.status)
        ).all()
    )
    data = survey.to_dict(include_questions=False)
    data["responses"] = {
        "completed": counts.get(ResponseStatus.COMPLETED.value, 0),
        "in_progress": counts.get(ResponseStatus.IN_PROGRESS.value, 0),
        "total": sum(counts.values()),
    }
    return data


@bp.get("")
@org_required()
def list_surveys():
    query = select(Survey).where(Survey.org_id == g.org.id)
    if status := request.args.get("status"):
        query = query.where(Survey.status == status)
    if q := request.args.get("q", "").strip():
        like = f"%{q}%"
        query = query.where(or_(Survey.title.ilike(like), Survey.description.ilike(like)))
    return jsonify(paginate(query.order_by(Survey.updated_at.desc()), _with_stats))


@bp.post("")
@org_required(Role.EDITOR)
def create_survey():
    data = parse(SurveyCreateIn)
    survey = survey_service.create_survey(
        g.org,
        title=data.title,
        description=data.description,
        questions=data.questions,
        settings=data.settings,
        created_by_id=actor_id(),
    )
    return jsonify(survey.to_dict()), 201


def _create_from_generated(generated: dict, source: dict) -> Survey:
    return survey_service.create_survey(
        g.org,
        title=generated["title"],
        description=generated.get("description", ""),
        questions=generated["questions"],
        settings={"welcome_message": generated.get("welcome_message", "")},
        source=source,
        created_by_id=actor_id(),
    )


@bp.post("/generate")
@org_required(Role.EDITOR)
@limiter.limit("20/hour")
def generate_survey():
    data = parse(GenerateSurveyIn)
    require_feature(g.org, "ai_builder")
    require_quota(g.org, "ai_generations")
    try:
        generated = generate_from_prompt(data.prompt, data.question_count)
    except AIError as exc:
        raise APIError(str(exc), code="ai_error", status=502) from exc
    survey = _create_from_generated(generated, {"type": "ai", "prompt": data.prompt[:500]})
    record_usage(g.org.id, "ai_generations", 1, ref_id=survey.id)
    db.session.commit()
    return jsonify(survey.to_dict()), 201


@bp.post("/import/google-form")
@org_required(Role.EDITOR)
@limiter.limit("30/hour")
def import_from_google_form():
    data = parse(ImportGoogleFormIn)
    require_feature(g.org, "import")
    parsed = import_google_form(str(data.url))
    questions = []
    for raw in parsed["questions"]:
        try:
            questions.append(QuestionIn.model_validate(raw))
        except ValidationError:
            continue  # skip the odd malformed item rather than failing the whole import
    if not questions:
        raise APIError("No supported questions were found in that form", code="form_empty")
    survey = survey_service.create_survey(
        g.org,
        title=parsed["title"][:200],
        description=parsed["description"][:5000],
        questions=questions,
        source={"type": "google_form", "url": parsed["url"]},
        created_by_id=actor_id(),
    )
    return jsonify(survey.to_dict()), 201


@bp.post("/import/pdf")
@org_required(Role.EDITOR)
@limiter.limit("20/hour")
def import_from_pdf():
    require_feature(g.org, "import")
    require_quota(g.org, "ai_generations")
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise APIError("Attach a PDF in the 'file' field", code="missing_file")
    text, fields = extract_pdf(upload.read())
    try:
        generated = generate_from_document(text, upload.filename, fields)
    except AIError as exc:
        raise APIError(str(exc), code="ai_error", status=502) from exc
    survey = _create_from_generated(generated, {"type": "pdf", "filename": upload.filename[:200]})
    record_usage(g.org.id, "ai_generations", 1, ref_id=survey.id)
    db.session.commit()
    return jsonify(survey.to_dict()), 201


@bp.get("/<survey_id>")
@org_required()
def get_survey_detail(survey_id: str):
    survey = get_survey(survey_id)
    data = {**survey.to_dict(), **_with_stats(survey)}
    data["settings"] = survey_service.merged_settings(survey)
    return jsonify(data)


@bp.patch("/<survey_id>")
@org_required(Role.EDITOR)
def update_survey(survey_id: str):
    survey = get_survey(survey_id)
    data = parse(SurveyUpdateIn)
    if data.title is not None:
        survey.title = data.title
    if data.description is not None:
        survey.description = data.description
    if data.settings is not None:
        settings = data.settings.model_dump(mode="json")
        if "voice" in settings["modes"]:
            require_feature(g.org, "voice")
        survey.settings = settings
    db.session.commit()
    return get_survey_detail(survey_id)


@bp.put("/<survey_id>/questions")
@org_required(Role.EDITOR)
def replace_questions(survey_id: str):
    survey = get_survey(survey_id)
    data = parse(QuestionsReplaceIn)
    survey_service.replace_questions(survey, data.questions)
    return get_survey_detail(survey_id)


@bp.delete("/<survey_id>")
@org_required(Role.EDITOR)
def delete_survey(survey_id: str):
    db.session.delete(get_survey(survey_id))
    db.session.commit()
    return "", 204


@bp.post("/<survey_id>/publish")
@org_required(Role.EDITOR)
def publish_survey(survey_id: str):
    survey = survey_service.publish(get_survey(survey_id), g.org)
    dispatch_event(g.org.id, "survey.published", survey.to_dict(include_questions=False))
    return get_survey_detail(survey.id)


@bp.post("/<survey_id>/close")
@org_required(Role.EDITOR)
def close_survey(survey_id: str):
    survey = survey_service.close(get_survey(survey_id))
    dispatch_event(g.org.id, "survey.closed", survey.to_dict(include_questions=False))
    return get_survey_detail(survey.id)


@bp.post("/<survey_id>/duplicate")
@org_required(Role.EDITOR)
def duplicate_survey(survey_id: str):
    copy = survey_service.duplicate(get_survey(survey_id), actor_id())
    return jsonify(copy.to_dict()), 201


@bp.get("/<survey_id>/analytics")
@org_required()
def analytics(survey_id: str):
    return jsonify(survey_analytics(get_survey(survey_id)))


@bp.post("/<survey_id>/insights")
@org_required(Role.EDITOR)
@limiter.limit("10/hour")
def insights(survey_id: str):
    survey = get_survey(survey_id)
    require_feature(g.org, "insights")
    require_quota(g.org, "ai_generations")
    stats = survey_analytics(survey)
    if stats["summary"]["completed"] == 0:
        raise APIError("Collect at least one completed response first", code="no_responses")
    text_ids = {q.id for q in survey.active_questions if q.type in (QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT)}
    text_answers: dict[str, list[str]] = {}
    completed = db.session.scalars(
        select(Response)
        .where(Response.survey_id == survey.id, Response.status == ResponseStatus.COMPLETED.value)
        .order_by(Response.completed_at.desc())
        .limit(500)
    )
    for response in completed:
        for answer in response.answers:
            if answer.question_id in text_ids:
                text_answers.setdefault(answer.question_id, []).append(str(answer.value))
    try:
        result = generate_insights(survey, stats, text_answers)
    except AIError as exc:
        raise APIError(str(exc), code="ai_error", status=502) from exc
    record_usage(g.org.id, "ai_generations", 1, ref_id=survey.id)
    db.session.commit()
    return jsonify(result)


@bp.get("/<survey_id>/outreach")
@org_required()
def list_outreach(survey_id: str):
    survey = get_survey(survey_id)
    query = select(Outreach).where(Outreach.survey_id == survey.id).order_by(Outreach.created_at.desc())
    return jsonify(paginate(query, lambda o: o.to_dict()))


@bp.post("/<survey_id>/outreach")
@org_required(Role.EDITOR)
def create_outreach(survey_id: str):
    survey = get_survey(survey_id)
    data = parse(OutreachIn)
    require_feature(g.org, "phone")
    created = queue_outreach(survey, g.org, [c.model_dump() for c in data.contacts])
    return jsonify({"items": [o.to_dict() for o in created]}), 201
