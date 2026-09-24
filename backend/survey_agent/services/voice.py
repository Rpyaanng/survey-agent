"""Voice interviews via ElevenLabs Conversational AI.

Two entry points share one agent:

* **Browser voice**: the respondent talks to the agent from the survey page. We
  mint a signed WebSocket URL and hand the agent the survey through dynamic
  variables.
* **Outbound phone**: we ask ElevenLabs (backed by Twilio) to call a contact.

Either way, when the call ends ElevenLabs POSTs the transcript to our
post-call webhook. We verify its HMAC signature, store the transcript, and
extract structured answers in the background. The agent's system prompt lives
in ``docs/voice-agent-prompt.md`` and uses the variables built by
``dynamic_variables``.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import math
import time
from typing import Any

import requests
from flask import current_app
from sqlalchemy import select

from ..ai.common import TONE_GUIDE, describe_questions
from ..ai.extraction import extract_answers
from ..ai.provider import AIError
from ..billing.entitlements import record_usage, require_quota
from ..errors import APIError, PlanLimitError
from ..extensions import db
from ..models import Channel, Organization, Outreach, Response, ResponseStatus, Survey
from ..tasks import enqueue
from ..utils import iso, utcnow
from .answers import AnswerError
from .responses import complete_response, create_response, fail_response, save_answer

logger = logging.getLogger(__name__)

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
SIGNATURE_TOLERANCE_SECONDS = 30 * 60


def voice_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("ELEVENLABS_API_KEY") and cfg.get("ELEVENLABS_AGENT_ID"))


def _headers() -> dict[str, str]:
    return {"xi-api-key": current_app.config["ELEVENLABS_API_KEY"]}


def dynamic_variables(survey: Survey, response: Response) -> dict[str, str]:
    settings = survey.settings or {}
    agent = settings.get("agent") or {}
    org = db.session.get(Organization, survey.org_id)
    return {
        "response_id": response.id,
        "survey_title": survey.title,
        "survey_description": survey.description or "",
        "organization_name": org.name if org else "",
        "agent_name": agent.get("name") or "Ava",
        "agent_tone": TONE_GUIDE.get(agent.get("tone", "friendly"), TONE_GUIDE["friendly"]),
        "agent_instructions": agent.get("instructions", ""),
        "welcome_message": settings.get("welcome_message") or f"Thanks for taking the {survey.title} survey.",
        "closing_message": settings.get("closing_message") or "Thanks so much for your time!",
        "questions": describe_questions(survey.active_questions, include_id=False),
        "respondent_name": (response.respondent or {}).get("name", ""),
    }


def start_browser_session(survey: Survey, respondent: dict) -> dict[str, Any]:
    if not voice_configured():
        raise APIError("Voice interviews are not configured on this server", code="voice_unavailable", status=503)
    org = db.session.get(Organization, survey.org_id)
    require_quota(org, "voice_minutes")
    response, token = create_response(survey, Channel.VOICE, respondent)
    try:
        resp = requests.get(
            f"{ELEVENLABS_API}/convai/conversation/get-signed-url",
            params={"agent_id": current_app.config["ELEVENLABS_AGENT_ID"]},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        signed_url = resp.json()["signed_url"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        fail_response(response, f"Could not start voice session: {exc}")
        raise APIError("Couldn't start a voice session, please try again", code="voice_unavailable", status=502) from exc
    return {
        "response_id": response.id,
        "response_token": token,
        "signed_url": signed_url,
        "dynamic_variables": dynamic_variables(survey, response),
    }


# ------------------------------------------------------------------ outbound
def queue_outreach(survey: Survey, org: Organization, contacts: list[dict[str, str]]) -> list[Outreach]:
    if not (voice_configured() and current_app.config.get("ELEVENLABS_PHONE_NUMBER_ID")):
        raise APIError("Phone interviews are not configured on this server", code="voice_unavailable", status=503)
    if survey.status != "published":
        raise APIError("Publish the survey before calling respondents", code="survey_not_published")
    require_quota(org, "voice_minutes")
    seen: set[str] = set()
    created: list[Outreach] = []
    for contact in contacts:
        if contact["phone"] in seen:
            continue
        seen.add(contact["phone"])
        outreach = Outreach(survey_id=survey.id, org_id=org.id, name=contact.get("name", ""), phone=contact["phone"])
        db.session.add(outreach)
        created.append(outreach)
    db.session.commit()
    for outreach in created:
        enqueue(place_call, outreach.id)
    return created


def place_call(outreach_id: str) -> None:
    outreach = db.session.get(Outreach, outreach_id)
    if outreach is None or outreach.status != "queued":
        return
    survey = db.session.get(Survey, outreach.survey_id)
    try:
        response, _ = create_response(
            survey, Channel.PHONE, {"name": outreach.name, "phone": outreach.phone}, outreach_id=outreach.id
        )
    except (APIError, PlanLimitError) as exc:
        outreach.status, outreach.error = "failed", exc.message
        db.session.commit()
        return
    outreach.response_id = response.id
    cfg = current_app.config
    try:
        resp = requests.post(
            f"{ELEVENLABS_API}/convai/twilio/outbound-call",
            headers=_headers(),
            json={
                "agent_id": cfg["ELEVENLABS_AGENT_ID"],
                "agent_phone_number_id": cfg["ELEVENLABS_PHONE_NUMBER_ID"],
                "to_number": outreach.phone,
                "conversation_initiation_client_data": {"dynamic_variables": dynamic_variables(survey, response)},
            },
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Outbound call to %s failed: %s", outreach.phone, exc)
        outreach.status, outreach.error = "failed", "The call could not be placed"
        fail_response(response, f"Outbound call failed: {exc}")
        return
    conversation_id = payload.get("conversation_id") or (payload.get("data") or {}).get("conversation_id")
    outreach.status = "calling"
    outreach.conversation_id = conversation_id
    response.conversation_id = conversation_id
    db.session.commit()


# ------------------------------------------------------------------ webhooks
def verify_signature(header: str | None, payload: bytes) -> bool:
    """Validate ElevenLabs' ``t=<ts>,v0=<hmac>`` signature over ``f"{ts}.{body}"``."""
    secret = current_app.config.get("ELEVENLABS_WEBHOOK_SECRET")
    if not secret or not header:
        return False
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
        signature = parts["v0"]
    except (ValueError, KeyError):
        return False
    if timestamp < int(time.time()) - SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.{payload.decode('utf-8')}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _normalize_transcript(raw: list[dict] | None) -> list[dict[str, str]]:
    turns = []
    for entry in raw or []:
        text = (entry.get("message") or "").strip()
        if not text:
            continue
        role = "agent" if entry.get("role") == "agent" else "respondent"
        turns.append({"role": role, "text": text, "at": iso(utcnow())})
    return turns


def handle_post_call(event: dict[str, Any]) -> str:
    """Store the transcript and queue answer extraction. Returns a status string."""
    data = event.get("data") or {}
    variables = ((data.get("conversation_initiation_client_data") or {}).get("dynamic_variables")) or {}
    response = None
    if variables.get("response_id"):
        response = db.session.get(Response, variables["response_id"])
    if response is None and data.get("conversation_id"):
        response = db.session.scalar(select(Response).where(Response.conversation_id == data["conversation_id"]))
    if response is None:
        return "unknown_response"
    if response.status != ResponseStatus.IN_PROGRESS.value:
        return "already_processed"  # webhooks can be retried; stay idempotent

    duration = int(((data.get("metadata") or {}).get("call_duration_secs")) or 0)
    response.transcript = _normalize_transcript(data.get("transcript"))
    response.conversation_id = response.conversation_id or data.get("conversation_id")
    response.meta = {**(response.meta or {}), "call_duration_seconds": duration}
    response.status = ResponseStatus.PROCESSING.value
    if duration:
        record_usage(response.org_id, "voice_minutes", math.ceil(duration / 60), ref_id=response.id)
    db.session.commit()
    enqueue(analyze_call, response.id)
    return "queued"


def analyze_call(response_id: str) -> None:
    response = db.session.get(Response, response_id)
    if response is None or response.status != ResponseStatus.PROCESSING.value:
        return
    outreach = db.session.get(Outreach, response.outreach_id) if response.outreach_id else None

    if not any(t["role"] == "respondent" for t in response.transcript or []):
        response.status = ResponseStatus.ABANDONED.value
        response.error = "The respondent didn't say anything"
        if outreach:
            outreach.status, outreach.error = "failed", "No answer"
        db.session.commit()
        return

    try:
        extracted = extract_answers(response.survey, response.transcript)
    except AIError as exc:
        response.status = ResponseStatus.FAILED.value
        response.error = f"Answer extraction failed: {exc}"
        if outreach:
            outreach.status, outreach.error = "failed", "Transcript analysis failed"
        db.session.commit()
        return

    questions = {q.id: q for q in response.survey.active_questions}
    rejected = []
    for item in extracted:
        question = questions.get(item.get("question_id"))
        if question is None:
            continue
        try:
            save_answer(response, question, item.get("value"), raw_text=item.get("raw_text") or None)
        except AnswerError as exc:
            rejected.append({"question_id": question.id, "value": item.get("value"), "reason": str(exc)})
    if rejected:
        response.meta = {**(response.meta or {}), "rejected_answers": rejected}
    if outreach:
        outreach.status = "completed"
    complete_response(response)


def inbound_call_variables(caller_number: str) -> dict[str, str] | None:
    """For inbound calls, match the caller to their pending outreach and start a response."""
    digits = "".join(ch for ch in caller_number if ch.isdigit())
    candidates = db.session.scalars(
        select(Outreach).where(Outreach.status.in_(["queued", "failed"])).order_by(Outreach.created_at.desc())
    ).all()
    outreach = next((o for o in candidates if "".join(c for c in o.phone if c.isdigit()) == digits), None)
    if outreach is None:
        return None
    survey = db.session.get(Survey, outreach.survey_id)
    try:
        response, _ = create_response(
            survey, Channel.PHONE, {"name": outreach.name, "phone": outreach.phone}, outreach_id=outreach.id
        )
    except (APIError, PlanLimitError):
        return None
    outreach.status, outreach.error, outreach.response_id = "calling", None, response.id
    db.session.commit()
    return dynamic_variables(survey, response)
