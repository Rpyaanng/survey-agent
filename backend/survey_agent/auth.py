"""Authentication and tenant resolution.

Three ways to authenticate:

* **Session cookie**: a signed JWT in an httpOnly cookie, set on login. Browsers
  reach the API through the frontend's same-origin ``/api`` proxy. Mutating
  requests must carry ``X-Requested-With``; cross-site forms can't set custom
  headers, so this blocks CSRF.
* **Bearer JWT**: the same token in an ``Authorization`` header, for non-browser
  clients.
* **API key**: ``Authorization: Bearer sa_live_...``. Bound to one organization
  with editor-level access. Requires a plan with ``api_access``.

The organization for a user request comes from the ``X-Org-Id`` header, falling
back to the user's default org.
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Callable

import jwt
from flask import current_app, g, request
from sqlalchemy import select

from .errors import Forbidden, Unauthorized
from .extensions import db
from .models import ApiKey, Membership, Organization, Role, User
from .utils import sha256, utcnow

API_KEY_PREFIX = "sa_live_"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def issue_token(user: User) -> str:
    now = int(time.time())  # epoch seconds; naive datetimes would be read as local time
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + int(current_app.config["AUTH_TOKEN_TTL"].total_seconds()),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def set_session_cookie(response, user: User):
    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME"],
        issue_token(user),
        max_age=int(current_app.config["AUTH_TOKEN_TTL"].total_seconds()),
        httponly=True,
        secure=current_app.config["AUTH_COOKIE_SECURE"],
        samesite="Lax",
        path="/",
    )
    return response


def clear_session_cookie(response):
    response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"], path="/")
    return response


def _authenticate() -> None:
    """Populate g.user / g.api_key from the request, or raise Unauthorized."""
    g.user = None
    g.api_key = None
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token.startswith(API_KEY_PREFIX):
            key = db.session.scalar(select(ApiKey).where(ApiKey.key_hash == sha256(token)))
            if key is None or key.revoked_at is not None:
                raise Unauthorized("Invalid API key")
            key.last_used_at = utcnow()
            g.api_key = key
            return
        user_id = _decode_token(token)
    else:
        cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
        if not cookie:
            raise Unauthorized("Authentication required")
        if request.method not in _SAFE_METHODS and not request.headers.get("X-Requested-With"):
            raise Forbidden("Missing X-Requested-With header", code="csrf_failed")
        user_id = _decode_token(cookie)

    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        raise Unauthorized("Session expired, please sign in again", code="session_expired")
    g.user = user


def login_required(fn: Callable) -> Callable:
    """Require a signed-in user (API keys are not accepted)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        _authenticate()
        if g.user is None:
            raise Forbidden("This endpoint requires a user session")
        return fn(*args, **kwargs)

    return wrapper


def _resolve_org_for_user(user: User) -> tuple[Organization, Membership]:
    requested = request.headers.get("X-Org-Id") or user.default_org_id
    memberships = user.memberships
    if not memberships:
        raise Forbidden("You don't belong to any organization", code="no_organization")
    membership = next((m for m in memberships if m.org_id == requested), None)
    if membership is None:
        if request.headers.get("X-Org-Id"):
            raise Forbidden("You are not a member of that organization")
        membership = memberships[0]
    return membership.organization, membership


def org_required(min_role: Role | str = Role.VIEWER, *, allow_api_key: bool = True) -> Callable:
    """Resolve ``g.org`` and ``g.role`` and enforce a minimum role."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _authenticate()
            if g.api_key is not None:
                if not allow_api_key:
                    raise Forbidden("API keys can't access this endpoint")
                org = db.session.get(Organization, g.api_key.org_id)
                from .billing.entitlements import require_feature

                require_feature(org, "api_access")
                g.org, g.role = org, Role.EDITOR
            else:
                g.org, membership = _resolve_org_for_user(g.user)
                g.role = membership.role_enum
            if not g.role.at_least(min_role):
                raise Forbidden(f"This action requires the {Role(min_role).value} role or higher")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def actor_id() -> str | None:
    return g.user.id if getattr(g, "user", None) else None


def touch_login(user: User) -> None:
    user.last_login_at = utcnow()
