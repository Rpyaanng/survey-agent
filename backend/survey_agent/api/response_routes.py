"""Browsing, exporting and deleting collected responses."""
from __future__ import annotations

import csv
import io
import re

from flask import Blueprint, Response as FlaskResponse, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..auth import org_required
from ..billing.entitlements import require_feature
from ..extensions import db
from ..models import Response, ResponseStatus, Role
from ..services.answers import format_answer
from ..services.responses import response_payload
from .common import get_response, get_survey, paginate

bp = Blueprint("responses", __name__, url_prefix="/api/v1")


@bp.get("/surveys/<survey_id>/responses")
@org_required()
def list_responses(survey_id: str):
    survey = get_survey(survey_id)
    query = (
        select(Response)
        .where(Response.survey_id == survey.id)
        .options(selectinload(Response.answers))
        .order_by(Response.started_at.desc())
    )
    if status := request.args.get("status"):
        query = query.where(Response.status == status)
    if channel := request.args.get("channel"):
        query = query.where(Response.channel == channel)
    return jsonify(paginate(query, lambda r: r.to_dict()))


@bp.get("/responses/<response_id>")
@org_required()
def get_response_detail(response_id: str):
    response = get_response(response_id)
    return jsonify(response.to_dict(include_detail=True))


@bp.delete("/responses/<response_id>")
@org_required(Role.EDITOR)
def delete_response(response_id: str):
    db.session.delete(get_response(response_id))
    db.session.commit()
    return "", 204


@bp.get("/surveys/<survey_id>/export")
@org_required()
def export_responses(survey_id: str):
    survey = get_survey(survey_id)
    require_feature(g.org, "export")
    fmt = request.args.get("format", "csv")
    status = request.args.get("status", ResponseStatus.COMPLETED.value)
    query = select(Response).where(Response.survey_id == survey.id).options(selectinload(Response.answers))
    if status != "all":
        query = query.where(Response.status == status)
    responses = db.session.scalars(query.order_by(Response.started_at)).all()
    filename = re.sub(r"[^A-Za-z0-9_-]+", "-", survey.title).strip("-")[:60] or "survey"

    if fmt == "json":
        body = jsonify({"survey": survey.to_dict(), "responses": [response_payload(r) for r in responses]})
        body.headers["Content-Disposition"] = f'attachment; filename="{filename}.json"'
        return body

    # Include archived questions that still hold answers so exports never lose data.
    answered_ids = {a.question_id for r in responses for a in r.answers}
    questions = [q for q in survey.questions if not q.archived or q.id in answered_ids]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["response_id", "status", "channel", "started_at", "completed_at", "respondent_name", "respondent_email"]
        + [q.title + (" (archived)" if q.archived else "") for q in questions]
    )
    for r in responses:
        answers = r.answers_by_question()
        respondent = r.respondent or {}
        writer.writerow(
            [
                r.id, r.status, r.channel,
                r.started_at.isoformat() if r.started_at else "",
                r.completed_at.isoformat() if r.completed_at else "",
                respondent.get("name", ""), respondent.get("email", ""),
            ]
            + [_csv_safe(format_answer(q, answers[q.id].value)) if q.id in answers else "" for q in questions]
        )
    return FlaskResponse(
        "﻿" + buffer.getvalue(),  # BOM so Excel detects UTF-8
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection from respondent-supplied text."""
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value  # plain numbers (including negatives) are safe
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
