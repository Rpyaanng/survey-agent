"""Subscription status, plan catalog, Stripe Checkout and Customer Portal."""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify

from ..auth import org_required
from ..billing import stripe_service
from ..billing.entitlements import effective_plan, ensure_subscription, usage_summary
from ..billing.plans import FEATURES, PLANS
from ..errors import APIError
from ..extensions import db
from ..models import Role
from ..schemas import CheckoutIn
from .common import parse

bp = Blueprint("billing", __name__, url_prefix="/api/v1/billing")


@bp.get("")
@org_required(allow_api_key=False)
def get_billing():
    sub = ensure_subscription(g.org)
    db.session.commit()
    plan = effective_plan(g.org)
    return jsonify({
        "subscription": sub.to_dict(),
        "plan": plan.to_dict(),
        "usage": usage_summary(g.org),
        "plans": [p.to_dict() for p in PLANS.values()],
        "features": FEATURES,
        "stripe_enabled": stripe_service.stripe_enabled(),
        "can_manage": g.role.at_least(Role.ADMIN),
    })


@bp.post("/checkout")
@org_required(Role.ADMIN, allow_api_key=False)
def checkout():
    data = parse(CheckoutIn)
    if stripe_service.stripe_enabled():
        return jsonify({"url": stripe_service.create_checkout_session(g.org, data.plan, g.user.email)})
    if not current_app.config.get("ALLOW_DEV_BILLING"):
        raise APIError("Billing is not configured", code="billing_not_configured", status=503)
    # Development mode: switch plans instantly without payment.
    sub = ensure_subscription(g.org)
    sub.plan, sub.status, sub.cancel_at_period_end = data.plan, "active", False
    db.session.commit()
    return jsonify({"url": None, "subscription": sub.to_dict(), "dev_mode": True})


@bp.post("/portal")
@org_required(Role.ADMIN, allow_api_key=False)
def portal():
    if stripe_service.stripe_enabled():
        return jsonify({"url": stripe_service.create_portal_session(g.org)})
    if not current_app.config.get("ALLOW_DEV_BILLING"):
        raise APIError("Billing is not configured", code="billing_not_configured", status=503)
    # Development mode: "cancel" returns the org to the free plan.
    sub = ensure_subscription(g.org)
    sub.plan, sub.status = "free", "active"
    db.session.commit()
    return jsonify({"url": None, "subscription": sub.to_dict(), "dev_mode": True})
