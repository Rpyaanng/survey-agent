"""Stripe integration: Checkout, Customer Portal and subscription webhooks.

Stripe is the system of record for payment state. Webhooks mirror it into the
``subscriptions`` table, which is what entitlement checks read.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
from flask import current_app
from sqlalchemy import select

from ..errors import APIError
from ..extensions import db
from ..models import Organization, Subscription
from .entitlements import ensure_subscription
from .plans import PLANS

logger = logging.getLogger(__name__)


def stripe_enabled() -> bool:
    return bool(current_app.config.get("STRIPE_SECRET_KEY"))


def _client() -> stripe.StripeClient:
    return stripe.StripeClient(current_app.config["STRIPE_SECRET_KEY"])


def price_for_plan(plan_id: str) -> str:
    price = {
        "pro": current_app.config.get("STRIPE_PRICE_PRO"),
        "team": current_app.config.get("STRIPE_PRICE_TEAM"),
    }.get(plan_id)
    if not price:
        raise APIError(f"No Stripe price configured for plan '{plan_id}'", code="billing_not_configured", status=503)
    return price


def plan_for_price(price_id: str | None) -> str | None:
    mapping = {
        current_app.config.get("STRIPE_PRICE_PRO"): "pro",
        current_app.config.get("STRIPE_PRICE_TEAM"): "team",
    }
    return mapping.get(price_id) if price_id else None


def _ensure_customer(client: stripe.StripeClient, org: Organization, email: str) -> str:
    if org.stripe_customer_id:
        return org.stripe_customer_id
    customer = client.v1.customers.create(params={"name": org.name, "email": email, "metadata": {"org_id": org.id}})
    org.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id


def create_checkout_session(org: Organization, plan_id: str, email: str) -> str:
    plan = PLANS.get(plan_id)
    if not plan or not plan.purchasable:
        raise APIError("That plan can't be purchased online", code="invalid_plan")
    client = _client()
    customer_id = _ensure_customer(client, org, email)
    frontend = current_app.config["FRONTEND_URL"]
    session = client.v1.checkout.sessions.create(
        params={
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": org.id,
            "line_items": [{"price": price_for_plan(plan_id), "quantity": 1}],
            "success_url": f"{frontend}/dashboard/settings/billing?checkout=success",
            "cancel_url": f"{frontend}/dashboard/settings/billing?checkout=cancelled",
            "allow_promotion_codes": True,
            "subscription_data": {"metadata": {"org_id": org.id, "plan": plan_id}},
            "metadata": {"org_id": org.id, "plan": plan_id},
        }
    )
    return session.url


def create_portal_session(org: Organization) -> str:
    if not org.stripe_customer_id:
        raise APIError("This organization has no billing account yet", code="no_billing_account")
    session = _client().v1.billing_portal.sessions.create(
        params={
            "customer": org.stripe_customer_id,
            "return_url": f"{current_app.config['FRONTEND_URL']}/dashboard/settings/billing",
        }
    )
    return session.url


def construct_event(payload: bytes, signature: str | None):
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise APIError("Stripe webhook secret not configured", code="billing_not_configured", status=503)
    try:
        return _client().construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise APIError("Invalid Stripe signature", code="invalid_signature") from exc


def handle_event(event) -> None:
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed" and obj.get("subscription"):
        sub = _client().v1.subscriptions.retrieve(obj["subscription"])
        org_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("org_id")
        sync_subscription(sub, org_id=org_id)
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        sync_subscription(obj)
    else:
        logger.debug("Ignoring Stripe event %s", event_type)


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, UTC).replace(tzinfo=None) if value else None


def sync_subscription(sub, org_id: str | None = None) -> Subscription | None:
    """Mirror a Stripe subscription object onto the org's local subscription row."""
    org = None
    if org_id:
        org = db.session.get(Organization, org_id)
    if org is None and (sub.get("metadata") or {}).get("org_id"):
        org = db.session.get(Organization, sub["metadata"]["org_id"])
    if org is None and sub.get("customer"):
        org = db.session.scalar(select(Organization).where(Organization.stripe_customer_id == sub["customer"]))
    if org is None:
        logger.warning("Stripe subscription %s has no matching organization", sub.get("id"))
        return None

    local = ensure_subscription(org)
    items = (sub.get("items") or {}).get("data") or []
    first_item = items[0] if items else {}
    price_id = (first_item.get("price") or {}).get("id")
    plan_id = plan_for_price(price_id) or (sub.get("metadata") or {}).get("plan") or local.plan

    status = sub.get("status", "active")
    local.stripe_subscription_id = sub.get("id")
    local.status = status
    local.plan = "free" if status in {"canceled", "incomplete_expired"} else plan_id
    local.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    # Newer Stripe API versions report billing periods on the subscription item.
    local.current_period_start = _ts(sub.get("current_period_start") or first_item.get("current_period_start"))
    local.current_period_end = _ts(sub.get("current_period_end") or first_item.get("current_period_end"))
    if sub.get("customer") and not org.stripe_customer_id:
        org.stripe_customer_id = sub["customer"]
    if status in {"canceled", "incomplete_expired"}:
        local.stripe_subscription_id = None
        local.status = "active"
    db.session.commit()
    return local
