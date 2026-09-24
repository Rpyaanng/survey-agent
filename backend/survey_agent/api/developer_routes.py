"""API keys and outbound webhook endpoints (Team plan and up)."""
from __future__ import annotations

import secrets

from flask import Blueprint, g, jsonify
from sqlalchemy import select

from ..auth import API_KEY_PREFIX, org_required
from ..billing.entitlements import require_feature
from ..errors import APIError, NotFound
from ..extensions import db
from ..models import ApiKey, Role, WebhookEndpoint
from ..schemas import ApiKeyIn, WebhookIn, WebhookUpdateIn
from ..services.webhooks import check_destination, deliver
from ..utils import iso, new_id, sha256, utcnow
from .common import parse

bp = Blueprint("developer", __name__, url_prefix="/api/v1")


# ------------------------------------------------------------------ API keys
@bp.get("/api-keys")
@org_required(Role.ADMIN, allow_api_key=False)
def list_keys():
    keys = db.session.scalars(
        select(ApiKey).where(ApiKey.org_id == g.org.id, ApiKey.revoked_at.is_(None)).order_by(ApiKey.created_at.desc())
    ).all()
    return jsonify({"items": [k.to_dict() for k in keys]})


@bp.post("/api-keys")
@org_required(Role.ADMIN, allow_api_key=False)
def create_key():
    require_feature(g.org, "api_access")
    data = parse(ApiKeyIn)
    secret = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        org_id=g.org.id, name=data.name, prefix=secret[:12], key_hash=sha256(secret), created_by_id=g.user.id
    )
    db.session.add(key)
    db.session.commit()
    # The plaintext key is shown exactly once.
    return jsonify({**key.to_dict(), "key": secret}), 201


@bp.delete("/api-keys/<key_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def revoke_key(key_id: str):
    key = db.session.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == g.org.id))
    if key is None:
        raise NotFound("API key")
    key.revoked_at = utcnow()
    db.session.commit()
    return "", 204


# ------------------------------------------------------------------ webhooks
def _endpoint(endpoint_id: str) -> WebhookEndpoint:
    endpoint = db.session.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.org_id == g.org.id)
    )
    if endpoint is None:
        raise NotFound("Webhook")
    return endpoint


def _validate_url(url: str) -> str:
    if not check_destination(url):
        raise APIError("Webhook URLs must point to a public internet address", code="invalid_webhook_url")
    return url


@bp.get("/webhooks")
@org_required(Role.ADMIN, allow_api_key=False)
def list_webhooks():
    endpoints = db.session.scalars(select(WebhookEndpoint).where(WebhookEndpoint.org_id == g.org.id)).all()
    return jsonify({"items": [e.to_dict() for e in endpoints]})


@bp.post("/webhooks")
@org_required(Role.ADMIN, allow_api_key=False)
def create_webhook():
    require_feature(g.org, "webhooks")
    data = parse(WebhookIn)
    endpoint = WebhookEndpoint(
        org_id=g.org.id,
        url=_validate_url(str(data.url)),
        secret="whsec_" + secrets.token_urlsafe(24),
        events=list(dict.fromkeys(data.events)),
        active=data.active,
    )
    db.session.add(endpoint)
    db.session.commit()
    return jsonify(endpoint.to_dict(include_secret=True)), 201


@bp.patch("/webhooks/<endpoint_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def update_webhook(endpoint_id: str):
    endpoint = _endpoint(endpoint_id)
    data = parse(WebhookUpdateIn)
    if data.url is not None:
        endpoint.url = _validate_url(str(data.url))
    if data.events is not None:
        endpoint.events = list(dict.fromkeys(data.events))
    if data.active is not None:
        endpoint.active = data.active
        if data.active:
            endpoint.failure_count = 0
    db.session.commit()
    return jsonify(endpoint.to_dict())


@bp.get("/webhooks/<endpoint_id>/secret")
@org_required(Role.ADMIN, allow_api_key=False)
def reveal_secret(endpoint_id: str):
    return jsonify({"secret": _endpoint(endpoint_id).secret})


@bp.delete("/webhooks/<endpoint_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def delete_webhook(endpoint_id: str):
    db.session.delete(_endpoint(endpoint_id))
    db.session.commit()
    return "", 204


@bp.post("/webhooks/<endpoint_id>/test")
@org_required(Role.ADMIN, allow_api_key=False)
def test_webhook(endpoint_id: str):
    endpoint = _endpoint(endpoint_id)
    event = {"id": new_id("evt"), "type": "webhook.test", "created_at": iso(utcnow()), "data": {"message": "Hello from Survey Agent"}}
    status = deliver(endpoint.id, event)
    return jsonify({"delivered": status is not None and 200 <= status < 300, "status": status})
