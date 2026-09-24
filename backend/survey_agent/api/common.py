from __future__ import annotations

from typing import Any, TypeVar

from flask import g, request
from pydantic import BaseModel
from sqlalchemy import Select, func, select

from ..errors import NotFound
from ..extensions import db
from ..models import Response, Survey

M = TypeVar("M", bound=BaseModel)


def parse(model: type[M]) -> M:
    return model.model_validate(request.get_json(silent=True) or {})


def paginate(query: Select, serialize, *, max_per_page: int = 100) -> dict[str, Any]:
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 25, type=int), 1), max_per_page)
    total = db.session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.session.scalars(query.limit(per_page).offset((page - 1) * per_page)).all()
    return {"items": [serialize(i) for i in items], "page": page, "per_page": per_page, "total": total}


def get_survey(survey_id: str) -> Survey:
    """Fetch a survey scoped to the current tenant. Other orgs' surveys 404."""
    survey = db.session.scalar(select(Survey).where(Survey.id == survey_id, Survey.org_id == g.org.id))
    if survey is None:
        raise NotFound("Survey")
    return survey


def get_response(response_id: str) -> Response:
    response = db.session.scalar(select(Response).where(Response.id == response_id, Response.org_id == g.org.id))
    if response is None:
        raise NotFound("Response")
    return response
