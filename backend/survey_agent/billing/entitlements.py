"""Plan enforcement: feature gates, quotas and usage metering."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from ..errors import PlanLimitError
from ..extensions import db
from ..models import Invitation, Membership, Organization, Subscription, Survey, SurveyStatus, UsageEvent
from ..utils import utcnow
from .plans import FEATURE_MIN_PLAN, FEATURES, METRIC_LIMIT_KEY, METRICS, Plan, get_plan

# Stripe keeps retrying payment while past_due, so access continues during that window.
_ENTITLED_STATUSES = {"active", "trialing", "past_due"}


def ensure_subscription(org: Organization) -> Subscription:
    if org.subscription is None:
        org.subscription = Subscription(plan="free", status="active")
        db.session.flush()
    return org.subscription


def effective_plan(org: Organization) -> Plan:
    sub = org.subscription
    if sub is None or sub.status not in _ENTITLED_STATUSES:
        return get_plan("free")
    return get_plan(sub.plan)


def has_feature(org: Organization, feature: str) -> bool:
    return feature in effective_plan(org).features


def require_feature(org: Organization, feature: str) -> None:
    if not has_feature(org, feature):
        plan = FEATURE_MIN_PLAN.get(feature, "pro")
        raise PlanLimitError(
            f"{FEATURES.get(feature, feature)} requires the {plan.title()} plan or higher.",
            feature=feature,
            required_plan=plan,
        )


def period_start(org: Organization) -> datetime:
    sub = org.subscription
    now = utcnow()
    if sub and sub.current_period_start and sub.current_period_end and sub.current_period_end > now:
        return sub.current_period_start
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage(org: Organization, metric: str) -> int:
    total = db.session.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.org_id == org.id,
            UsageEvent.metric == metric,
            UsageEvent.created_at >= period_start(org),
        )
    )
    return int(total or 0)


def record_usage(org_id: str, metric: str, quantity: int = 1, ref_id: str | None = None) -> None:
    if quantity <= 0:
        return
    db.session.add(UsageEvent(org_id=org_id, metric=metric, quantity=quantity, ref_id=ref_id))


def remaining(org: Organization, metric: str) -> int | None:
    limit = effective_plan(org).limit(METRIC_LIMIT_KEY[metric])
    if limit is None:
        return None
    return max(limit - usage(org, metric), 0)


def require_quota(org: Organization, metric: str, amount: int = 1) -> None:
    left = remaining(org, metric)
    if left is not None and left < amount:
        plan = effective_plan(org)
        raise PlanLimitError(
            f"Your {plan.name} plan's monthly {metric.replace('_', ' ')} quota is used up.",
            feature=metric,
            required_plan=_next_plan(plan.id),
        )


def active_survey_count(org: Organization) -> int:
    return db.session.scalar(
        select(func.count()).select_from(Survey).where(
            Survey.org_id == org.id, Survey.status == SurveyStatus.PUBLISHED.value
        )
    ) or 0


def require_active_survey_slot(org: Organization) -> None:
    limit = effective_plan(org).limit("active_surveys")
    if limit is not None and active_survey_count(org) >= limit:
        raise PlanLimitError(
            f"Your plan allows {limit} live surveys. Close one or upgrade.",
            feature="active_surveys",
            required_plan=_next_plan(effective_plan(org).id),
        )


def seats_used(org: Organization) -> int:
    members = db.session.scalar(
        select(func.count()).select_from(Membership).where(Membership.org_id == org.id)
    ) or 0
    pending = db.session.scalar(
        select(func.count()).select_from(Invitation).where(
            Invitation.org_id == org.id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > utcnow(),
        )
    ) or 0
    return members + pending


def require_seat(org: Organization) -> None:
    limit = effective_plan(org).limit("seats")
    if limit is not None and seats_used(org) >= limit:
        raise PlanLimitError(
            f"Your plan includes {limit} seat{'s' if limit != 1 else ''}. Upgrade to add teammates.",
            feature="seats",
            required_plan=_next_plan(effective_plan(org).id),
        )


def usage_summary(org: Organization) -> dict:
    plan = effective_plan(org)
    summary = {
        metric: {"used": usage(org, metric), "limit": plan.limit(METRIC_LIMIT_KEY[metric])} for metric in METRICS
    }
    summary["active_surveys"] = {"used": active_survey_count(org), "limit": plan.limit("active_surveys")}
    summary["seats"] = {"used": seats_used(org), "limit": plan.limit("seats")}
    summary["period_start"] = period_start(org).isoformat() + "Z"
    return summary


def _next_plan(plan_id: str) -> str:
    return {"free": "pro", "pro": "team"}.get(plan_id, "enterprise")
