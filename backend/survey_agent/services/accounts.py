"""Organizations, memberships and invitations."""
from __future__ import annotations

from flask import current_app
from sqlalchemy import select

from ..billing.entitlements import effective_plan, require_seat
from ..errors import APIError, Conflict, Forbidden, NotFound
from ..extensions import db
from ..models import Invitation, Membership, Organization, Role, Subscription, User
from ..utils import new_token, sha256, slugify, utcnow
from .email import render_email, send_email


def _unique_slug(name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while db.session.scalar(select(Organization.id).where(Organization.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


def create_organization(name: str, owner: User) -> Organization:
    org = Organization(name=name, slug=_unique_slug(name))
    org.subscription = Subscription(plan="free", status="active")
    db.session.add(org)
    db.session.flush()
    db.session.add(Membership(org_id=org.id, user_id=owner.id, role=Role.OWNER.value))
    owner.default_org_id = org.id
    db.session.flush()
    return org


def org_summary(org: Organization, role: str) -> dict:
    return {**org.to_dict(), "role": role, "plan": effective_plan(org).id}


def user_context(user: User) -> dict:
    return {
        "user": user.to_dict(),
        "organizations": [org_summary(m.organization, m.role) for m in user.memberships],
        "default_org_id": user.default_org_id,
    }


def invite_member(org: Organization, email: str, role: str, invited_by: User) -> Invitation:
    email = email.lower()
    existing_member = db.session.scalar(
        select(Membership).join(User).where(Membership.org_id == org.id, User.email == email)
    )
    if existing_member:
        raise Conflict("That person is already a member", code="already_member")
    pending = db.session.scalars(
        select(Invitation).where(Invitation.org_id == org.id, Invitation.email == email, Invitation.accepted_at.is_(None))
    ).all()
    for inv in pending:  # re-inviting replaces the old link
        db.session.delete(inv)
    db.session.flush()
    require_seat(org)

    token = new_token(24)
    invitation = Invitation(org_id=org.id, email=email, role=role, token_hash=sha256(token), invited_by_id=invited_by.id)
    db.session.add(invitation)
    db.session.commit()

    link = f"{current_app.config['FRONTEND_URL']}/invite/{token}"
    send_email(
        email,
        f"You're invited to {org.name} on Survey Agent",
        render_email(
            f"Join {org.name}",
            [f"{invited_by.name or invited_by.email} invited you to collaborate on surveys as {role}."],
            ("Accept invitation", link),
        ),
    )
    invitation.accept_link = link  # transient: returned once so admins can share it manually
    return invitation


def find_invitation(token: str) -> Invitation:
    invitation = db.session.scalar(select(Invitation).where(Invitation.token_hash == sha256(token)))
    if invitation is None or not invitation.is_pending:
        raise NotFound("Invitation")
    return invitation


def accept_invitation(token: str, user: User) -> Membership:
    invitation = find_invitation(token)
    if invitation.email != user.email:
        raise Forbidden("This invitation was sent to a different email address", code="invitation_email_mismatch")
    membership = db.session.scalar(
        select(Membership).where(Membership.org_id == invitation.org_id, Membership.user_id == user.id)
    )
    if membership is None:
        membership = Membership(org_id=invitation.org_id, user_id=user.id, role=invitation.role)
        db.session.add(membership)
    invitation.accepted_at = utcnow()
    user.default_org_id = invitation.org_id
    db.session.commit()
    return membership


def change_role(org: Organization, membership: Membership, new_role: str, actor_role: Role) -> Membership:
    if new_role == Role.OWNER.value and actor_role != Role.OWNER:
        raise Forbidden("Only owners can grant the owner role")
    if membership.role == Role.OWNER.value and new_role != Role.OWNER.value:
        _ensure_another_owner(org, membership)
    if membership.role == Role.OWNER.value and actor_role != Role.OWNER:
        raise Forbidden("Only owners can change another owner's role")
    membership.role = new_role
    db.session.commit()
    return membership


def remove_member(org: Organization, membership: Membership, actor_role: Role) -> None:
    if membership.role == Role.OWNER.value:
        if actor_role != Role.OWNER:
            raise Forbidden("Only owners can remove an owner")
        _ensure_another_owner(org, membership)
    user = membership.user
    db.session.delete(membership)
    if user.default_org_id == org.id:
        other = next((m for m in user.memberships if m.org_id != org.id), None)
        user.default_org_id = other.org_id if other else None
    db.session.commit()


def _ensure_another_owner(org: Organization, membership: Membership) -> None:
    owners = [m for m in org.memberships if m.role == Role.OWNER.value and m.id != membership.id]
    if not owners:
        raise APIError("An organization must keep at least one owner", code="last_owner")
