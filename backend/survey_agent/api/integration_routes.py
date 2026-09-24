"""Inbound webhooks from Stripe and ElevenLabs. Each one is signature-verified."""
from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request

from ..billing import stripe_service
from ..errors import APIError, NotFound, Unauthorized
from ..services import voice

logger = logging.getLogger(__name__)

bp = Blueprint("integrations", __name__, url_prefix="/api/v1/integrations")


@bp.post("/stripe/webhook")
def stripe_webhook():
    event = stripe_service.construct_event(request.get_data(), request.headers.get("Stripe-Signature"))
    stripe_service.handle_event(event)
    return jsonify({"received": True})


@bp.post("/elevenlabs/post-call")
def elevenlabs_post_call():
    payload = request.get_data()
    if not voice.verify_signature(request.headers.get("elevenlabs-signature"), payload):
        raise Unauthorized("Invalid webhook signature", code="invalid_signature")
    try:
        event = json.loads(payload)
    except ValueError as exc:
        raise APIError("Invalid JSON payload") from exc
    if event.get("type") not in (None, "post_call_transcription"):
        return jsonify({"status": "ignored"})
    status = voice.handle_post_call(event)
    logger.info("ElevenLabs post-call webhook: %s", status)
    return jsonify({"status": status})


@bp.post("/elevenlabs/inbound-call")
def elevenlabs_inbound_call():
    """Conversation-initiation webhook for inbound calls. Returns the survey as dynamic variables."""
    if not voice.verify_signature(request.headers.get("elevenlabs-signature"), request.get_data()):
        raise Unauthorized("Invalid webhook signature", code="invalid_signature")
    data = request.get_json(silent=True) or {}
    variables = voice.inbound_call_variables(data.get("caller_id", ""))
    if variables is None:
        raise NotFound("Pending interview for this caller")
    return jsonify({"type": "conversation_initiation_client_data", "dynamic_variables": variables})
