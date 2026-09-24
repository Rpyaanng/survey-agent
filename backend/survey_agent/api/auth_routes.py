"""Registration, login and the current user's profile."""
from __future__ import annotations

from flask import Blueprint, g, jsonify
from sqlalchemy import select

from ..auth import clear_session_cookie, issue_token, login_required, set_session_cookie, touch_login
from ..errors import APIError, Conflict, Unauthorized
from ..extensions import db, limiter
from ..models import User
from ..schemas import LoginIn, ProfileUpdateIn, RegisterIn
from ..services.accounts import create_organization, user_context
from .common import parse

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@bp.post("/register")
@limiter.limit("10/hour")
def register():
    data = parse(RegisterIn)
    email = data.email.lower()
    if db.session.scalar(select(User).where(User.email == email)):
        raise Conflict("An account with this email already exists", code="email_taken")
    user = User(email=email, name=data.name or email.split("@")[0])
    user.set_password(data.password)
    db.session.add(user)
    db.session.flush()
    org_name = data.organization_name or f"{user.name}'s workspace"
    create_organization(org_name, owner=user)
    touch_login(user)
    db.session.commit()
    resp = jsonify({**user_context(user), "token": issue_token(user)})
    resp.status_code = 201
    return set_session_cookie(resp, user)


@bp.post("/login")
@limiter.limit("20/minute")
def login():
    data = parse(LoginIn)
    user = db.session.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not user.check_password(data.password):
        raise Unauthorized("Incorrect email or password", code="invalid_credentials")
    touch_login(user)
    db.session.commit()
    return set_session_cookie(jsonify({**user_context(user), "token": issue_token(user)}), user)


@bp.post("/logout")
def logout():
    return clear_session_cookie(jsonify({"ok": True}))


@bp.get("/me")
@login_required
def me():
    return jsonify(user_context(g.user))


@bp.patch("/me")
@login_required
def update_me():
    data = parse(ProfileUpdateIn)
    user = g.user
    if data.name is not None:
        user.name = data.name
    if data.new_password:
        if not data.current_password or not user.check_password(data.current_password):
            raise APIError("Current password is incorrect", code="invalid_password")
        user.set_password(data.new_password)
    db.session.commit()
    return jsonify(user_context(user))
