"""Respondent-facing endpoints. No login: responses are authorized by a per-response token."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..ai.interviewer import progress, run_chat_turn
from ..ai.provider import AIError
from ..billing.plans import PLANS
from ..errors import APIError, NotFound
from ..extensions import db, limiter
from ..models import Channel, Response, Survey, SurveyStatus
from ..schemas import ChatTurnIn, StartResponseIn, SubmitAnswersIn
from ..services.responses import (
    assert_accepting,
    create_response,
    save_form_answers,
    token_matches,
    verify_access,
)
from ..services.surveys import public_view
from ..services.voice import start_browser_session
from .common import parse

bp = Blueprint("public", __name__, url_prefix="/api/v1/public")


def _published_survey(token: str) -> Survey:
    survey = db.session.scalar(select(Survey).where(Survey.public_token == token))
    if survey is None or survey.status == SurveyStatus.DRAFT.value:
        raise NotFound("Survey")
    return survey


def _response_for(response_id: str) -> Response:
    response = db.session.get(Response, response_id)
    if response is None:
        raise NotFound("Response")
    verify_access(response, request.headers.get("X-Response-Token"))
    return response


@bp.get("/plans")
def plans():
    return jsonify({"plans": [p.to_dict() for p in PLANS.values()]})


@bp.get("/surveys/<token>")
@limiter.limit("120/minute")
def get_public_survey(token: str):
    survey = _published_survey(token)
    view = public_view(survey)
    try:
        assert_accepting(survey)
        view["accepting_responses"] = True
    except APIError:
        view["accepting_responses"] = False
    return jsonify(view)


@bp.post("/surveys/<token>/responses")
@limiter.limit("20/minute")
def start_response(token: str):
    survey = _published_survey(token)
    data = parse(StartResponseIn)
    if data.channel == "voice":
        return jsonify(start_browser_session(survey, data.respondent)), 201
    response, access_token = create_response(survey, data.channel_enum, data.respondent)
    return jsonify({"response_id": response.id, "response_token": access_token}), 201


@bp.get("/responses/<response_id>")
def response_status(response_id: str):
    response = db.session.get(Response, response_id)
    if response is None:
        raise NotFound("Response")
    # Polling continues after completion, so check only the token (not the in-progress rule).
    if not token_matches(response, request.headers.get("X-Response-Token")):
        raise NotFound("Response")
    return jsonify({"id": response.id, "status": response.status, "progress": progress(response)})


@bp.post("/responses/<response_id>/answers")
@limiter.limit("60/minute")
def submit_answers(response_id: str):
    response = _response_for(response_id)
    if response.channel != Channel.FORM.value:
        raise APIError("This response is not a form response", code="wrong_channel")
    data = parse(SubmitAnswersIn)
    errors = save_form_answers(response, data.answers, complete=data.complete)
    if errors:
        raise APIError("Some answers need attention", code="validation_error", status=422, details=errors)
    return jsonify({"status": response.status, "progress": progress(response)})


@bp.post("/responses/<response_id>/chat")
@limiter.limit("30/minute")
def chat_turn(response_id: str):
    response = _response_for(response_id)
    if response.channel != Channel.CHAT.value:
        raise APIError("This response is not a chat response", code="wrong_channel")
    data = parse(ChatTurnIn)
    try:
        result = run_chat_turn(response, data.message)
    except AIError as exc:
        db.session.rollback()
        raise APIError(str(exc), code="ai_error", status=502) from exc
    return jsonify(result)
