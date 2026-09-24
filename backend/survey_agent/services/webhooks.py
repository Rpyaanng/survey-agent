"""Outbound webhooks: signed event delivery to customer endpoints.

Each delivery is POSTed as JSON with the header
``X-SurveyAgent-Signature: t=<unix>,v1=<hex>``, where ``v1`` is
HMAC-SHA256(secret, f"{t}.{raw_body}"). Receivers should recompute the HMAC
and reject timestamps older than a few minutes.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
from typing import Any
from urllib.parse import urlparse

import requests
from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import WebhookEndpoint
from ..tasks import enqueue
from ..utils import iso, new_id, utcnow

logger = logging.getLogger(__name__)

AUTO_DISABLE_AFTER = 20


def is_public_url(url: str) -> bool:
    """Reject URLs resolving to private, loopback or link-local addresses (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def check_destination(url: str) -> bool:
    if current_app.config.get("APP_ENV") != "production":
        return True  # local receivers (localhost tunnels, test servers) are fine outside production
    return is_public_url(url)


def sign(secret: str, timestamp: int, body: str) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def dispatch_event(org_id: str, event_type: str, data: dict[str, Any]) -> int:
    """Queue delivery of ``event_type`` to every subscribed endpoint. Returns the count."""
    from ..billing.entitlements import has_feature
    from ..models import Organization

    org = db.session.get(Organization, org_id)
    if org is None or not has_feature(org, "webhooks"):
        return 0
    endpoints = db.session.scalars(
        select(WebhookEndpoint).where(WebhookEndpoint.org_id == org_id, WebhookEndpoint.active.is_(True))
    ).all()
    event = {"id": new_id("evt"), "type": event_type, "created_at": iso(utcnow()), "data": data}
    count = 0
    for endpoint in endpoints:
        if event_type in (endpoint.events or []):
            enqueue(deliver, endpoint.id, event)
            count += 1
    return count


def deliver(endpoint_id: str, event: dict[str, Any]) -> int | None:
    endpoint = db.session.get(WebhookEndpoint, endpoint_id)
    if endpoint is None:
        return None
    body = json.dumps(event, separators=(",", ":"), sort_keys=True)
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SurveyAgent-Webhooks/1.0",
        "X-SurveyAgent-Event": event["type"],
        "X-SurveyAgent-Signature": f"t={timestamp},v1={sign(endpoint.secret, timestamp, body)}",
    }
    status: int | None
    if not check_destination(endpoint.url):
        logger.warning("Blocked webhook delivery to non-public address %s", endpoint.url)
        status = None
    else:
        status = _post(endpoint.url, body, headers)

    endpoint.last_delivery_at = utcnow()
    endpoint.last_status = status
    if status is not None and 200 <= status < 300:
        endpoint.failure_count = 0
    else:
        endpoint.failure_count += 1
        if endpoint.failure_count >= AUTO_DISABLE_AFTER:
            endpoint.active = False
            logger.warning("Disabled webhook %s after %s consecutive failures", endpoint.id, AUTO_DISABLE_AFTER)
    db.session.commit()
    return status


def _post(url: str, body: str, headers: dict[str, str]) -> int | None:
    try:
        return requests.post(url, data=body, headers=headers, timeout=10, allow_redirects=False).status_code
    except requests.RequestException as exc:
        logger.warning("Webhook delivery to %s failed: %s", url, exc)
        return None
