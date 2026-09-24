"""Subscriptions, metered usage, API keys and outbound webhook endpoints."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils import iso, new_id, utcnow


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("sub"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    # active | trialing | past_due | canceled | incomplete
    status: Mapped[str] = mapped_column(String(32), default="active")
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    current_period_start: Mapped[datetime | None]
    current_period_end: Mapped[datetime | None]
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="subscription")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "plan": self.plan,
            "status": self.status,
            "current_period_start": iso(self.current_period_start),
            "current_period_end": iso(self.current_period_end),
            "cancel_at_period_end": self.cancel_at_period_end,
            "managed_by_stripe": bool(self.stripe_subscription_id),
        }


class UsageEvent(db.Model):
    """Append-only usage ledger; quotas are computed by summing the current period."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_org_metric_time", "org_id", "metric", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(48))
    quantity: Mapped[int] = mapped_column(default=1)
    ref_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("key"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": iso(self.created_at),
            "last_used_at": iso(self.last_used_at),
            "revoked_at": iso(self.revoked_at),
        }


class WebhookEndpoint(db.Model):
    __tablename__ = "webhook_endpoints"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("whk"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    secret: Mapped[str] = mapped_column(String(64))
    events: Mapped[list] = mapped_column(db.JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_delivery_at: Mapped[datetime | None]
    last_status: Mapped[int | None]
    failure_count: Mapped[int] = mapped_column(default=0)

    def to_dict(self, *, include_secret: bool = False) -> dict:
        data = {
            "id": self.id,
            "url": self.url,
            "events": self.events or [],
            "active": self.active,
            "created_at": iso(self.created_at),
            "last_delivery_at": iso(self.last_delivery_at),
            "last_status": self.last_status,
            "failure_count": self.failure_count,
        }
        if include_secret:
            data["secret"] = self.secret
        return data
