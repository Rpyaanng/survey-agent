"""Organization settings, members and invitations."""
from __future__ import annotations

from flask import Blueprint, g, jsonify
from sqlalchemy import select

from ..auth import login_required, org_required
from ..errors import NotFound
from ..extensions import db
from ..models import Invitation, Membership, Role
from ..schemas import InviteIn, MemberUpdateIn, OrgCreateIn, OrgUpdateIn
from ..services import accounts
from .common import parse

bp = Blueprint("orgs", __name__, url_prefix="/api/v1")


@bp.post("/orgs")
@login_required
def create_org():
    data = parse(OrgCreateIn)
    org = accounts.create_organization(data.name, owner=g.user)
    db.session.commit()
    return jsonify(accounts.org_summary(org, Role.OWNER.value)), 201


@bp.get("/org")
@org_required()
def get_org():
    return jsonify(accounts.org_summary(g.org, g.role.value))


@bp.patch("/org")
@org_required(Role.ADMIN, allow_api_key=False)
def update_org():
    data = parse(OrgUpdateIn)
    if data.name is not None:
        g.org.name = data.name
    if data.branding is not None:
        g.org.branding = data.branding.model_dump(mode="json", exclude_none=True)
    db.session.commit()
    return jsonify(accounts.org_summary(g.org, g.role.value))


@bp.get("/org/members")
@org_required(allow_api_key=False)
def list_members():
    members = db.session.scalars(
        select(Membership).where(Membership.org_id == g.org.id).order_by(Membership.created_at)
    ).all()
    invitations = []
    if g.role.at_least(Role.ADMIN):
        invitations = [
            i.to_dict()
            for i in db.session.scalars(select(Invitation).where(Invitation.org_id == g.org.id)).all()
            if i.is_pending
        ]
    return jsonify({"members": [m.to_dict() for m in members], "invitations": invitations})


def _membership(member_id: str) -> Membership:
    membership = db.session.scalar(
        select(Membership).where(Membership.id == member_id, Membership.org_id == g.org.id)
    )
    if membership is None:
        raise NotFound("Member")
    return membership


@bp.patch("/org/members/<member_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def update_member(member_id: str):
    data = parse(MemberUpdateIn)
    membership = accounts.change_role(g.org, _membership(member_id), data.role, g.role)
    return jsonify(membership.to_dict())


@bp.delete("/org/members/<member_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def delete_member(member_id: str):
    accounts.remove_member(g.org, _membership(member_id), g.role)
    return "", 204


@bp.post("/org/leave")
@org_required(allow_api_key=False)
def leave_org():
    membership = next(m for m in g.user.memberships if m.org_id == g.org.id)
    accounts.remove_member(g.org, membership, membership.role_enum)
    return "", 204


@bp.post("/org/invitations")
@org_required(Role.ADMIN, allow_api_key=False)
def create_invitation():
    data = parse(InviteIn)
    invitation = accounts.invite_member(g.org, data.email, data.role, g.user)
    return jsonify({**invitation.to_dict(), "accept_link": invitation.accept_link}), 201


@bp.delete("/org/invitations/<invitation_id>")
@org_required(Role.ADMIN, allow_api_key=False)
def revoke_invitation(invitation_id: str):
    invitation = db.session.scalar(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.org_id == g.org.id)
    )
    if invitation is None:
        raise NotFound("Invitation")
    db.session.delete(invitation)
    db.session.commit()
    return "", 204


@bp.get("/invitations/<token>")
def get_invitation(token: str):
    invitation = accounts.find_invitation(token)
    return jsonify({"email": invitation.email, "role": invitation.role, "organization": invitation.organization.name})


@bp.post("/invitations/<token>/accept")
@login_required
def accept(token: str):
    membership = accounts.accept_invitation(token, g.user)
    return jsonify(accounts.org_summary(membership.organization, membership.role))
