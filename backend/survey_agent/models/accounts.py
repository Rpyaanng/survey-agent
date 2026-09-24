"""Users, organizations (tenants), memberships and invitations."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..utils import iso, new_id, utcnow


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}[self.value]

    def at_least(self, other: "Role | str") -> bool:
        return self.rank >= Role(other).rank


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]
    default_org_id: Mapped[str | None] = mapped_column(String(32))

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "created_at": iso(self.created_at)}


class Organization(db.Model):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Branding shown on public survey pages: {"logo_url", "primary_color"}.
    branding: Mapped[dict] = mapped_column(db.JSON, default=dict)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship(  # noqa: F821
        back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "branding": self.branding or {},
            "created_at": iso(self.created_at),
        }


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("mem"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default=Role.VIEWER.value)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")

    @property
    def role_enum(self) -> Role:
        return Role(self.role)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "user": self.user.to_dict(),
            "created_at": iso(self.created_at),
        }


class Invitation(db.Model):
    __tablename__ = "invitations"

    TTL = timedelta(days=7)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("inv"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(16), default=Role.EDITOR.value)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(default=lambda: utcnow() + Invitation.TTL)
    accepted_at: Mapped[datetime | None]

    organization: Mapped[Organization] = relationship()

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and self.expires_at > utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "created_at": iso(self.created_at),
            "expires_at": iso(self.expires_at),
            "accepted_at": iso(self.accepted_at),
        }
