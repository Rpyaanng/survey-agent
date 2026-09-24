import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from survey_agent.billing.stripe_service import sync_subscription
from survey_agent.extensions import db
from survey_agent.models import Organization

from .conftest import ApiClient, make_survey, register


def test_billing_overview(app):
    api = register(app)
    billing = api.get("/api/v1/billing").get_json()
    assert billing["plan"]["id"] == "free"
    assert billing["usage"]["active_surveys"] == {"used": 0, "limit": 3}
    assert {p["id"] for p in billing["plans"]} == {"free", "pro", "team", "enterprise"}
    assert billing["stripe_enabled"] is False


def test_dev_checkout_switches_plan(app):
    api = register(app)
    assert api.get(f"/api/v1/surveys/x/export").status_code in (402, 404)
    res = api.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert res.status_code == 200
    assert res.get_json()["dev_mode"] is True
    assert api.get("/api/v1/billing").get_json()["plan"]["id"] == "pro"
    api.post("/api/v1/billing/portal")
    assert api.get("/api/v1/billing").get_json()["plan"]["id"] == "free"


def test_checkout_rejects_unpurchasable_plan(app):
    api = register(app)
    assert api.post("/api/v1/billing/checkout", json={"plan": "enterprise"}).status_code == 422


def test_feature_gates(app):
    api = register(app)
    survey = make_survey(api)
    res = api.get(f"/api/v1/surveys/{survey['id']}/export")
    assert res.status_code == 402
    assert res.get_json()["error"]["details"] == {"feature": "export", "required_plan": "pro"}
    assert api.post("/api/v1/api-keys", json={"name": "ci"}).status_code == 402


def test_stripe_sync_maps_price_to_plan(app):
    app.config.update(STRIPE_PRICE_PRO="price_pro", STRIPE_PRICE_TEAM="price_team")
    api = register(app)
    org = db.session.get(Organization, api.org_id)
    org.stripe_customer_id = "cus_123"
    db.session.commit()
    stripe_sub = {
        "id": "sub_1",
        "customer": "cus_123",
        "status": "active",
        "cancel_at_period_end": False,
        "metadata": {},
        "items": {"data": [{"price": {"id": "price_team"}, "current_period_start": 1767225600, "current_period_end": 1769904000}]},
    }
    local = sync_subscription(stripe_sub)
    assert local.plan == "team"
    assert local.current_period_start.year == 2026
    assert api.get("/api/v1/billing").get_json()["plan"]["id"] == "team"

    local = sync_subscription({**stripe_sub, "status": "canceled"})
    assert local.plan == "free"
    assert local.stripe_subscription_id is None


def test_past_due_keeps_access_but_unpaid_does_not(app):
    api = register(app, plan="pro")
    org = db.session.get(Organization, api.org_id)
    org.subscription.status = "past_due"
    db.session.commit()
    assert api.get("/api/v1/billing").get_json()["plan"]["id"] == "pro"
    org.subscription.status = "unpaid"
    db.session.commit()
    assert api.get("/api/v1/billing").get_json()["plan"]["id"] == "free"


def test_stripe_webhook_requires_configuration(app):
    res = app.test_client().post("/api/v1/integrations/stripe/webhook", data=b"{}")
    assert res.status_code == 503


# ------------------------------------------------------------------ API keys
def test_api_key_lifecycle(owner, app):
    make_survey(owner)
    created = owner.post("/api/v1/api-keys", json={"name": "Zapier"})
    assert created.status_code == 201
    key = created.get_json()["key"]
    assert key.startswith("sa_live_")

    client = app.test_client()
    listing = client.get("/api/v1/surveys", headers={"Authorization": f"Bearer {key}"})
    assert listing.status_code == 200
    assert listing.get_json()["total"] == 1
    # API keys have editor rights, but can't manage keys or billing.
    assert client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {key}"}).status_code == 403
    assert client.get("/api/v1/billing", headers={"Authorization": f"Bearer {key}"}).status_code == 403

    key_id = created.get_json()["id"]
    assert owner.delete(f"/api/v1/api-keys/{key_id}").status_code == 204
    assert client.get("/api/v1/surveys", headers={"Authorization": f"Bearer {key}"}).status_code == 401


def test_api_key_stops_working_after_downgrade(owner, app):
    key = owner.post("/api/v1/api-keys", json={"name": "k"}).get_json()["key"]
    owner.post("/api/v1/billing/portal")  # dev mode: downgrade to free
    res = app.test_client().get("/api/v1/surveys", headers={"Authorization": f"Bearer {key}"})
    assert res.status_code == 402


# ------------------------------------------------------------------ webhooks
def test_webhook_delivery_is_signed(owner):
    created = owner.post("/api/v1/webhooks", json={"url": "https://hooks.example.com/sa", "events": ["response.completed"]})
    assert created.status_code == 201
    secret = created.get_json()["secret"]
    survey = make_survey(owner, questions=[{"type": "short_text", "title": "Anything?"}])

    fake = MagicMock(status_code=200)
    with patch("survey_agent.services.webhooks.requests.post", return_value=fake) as post:
        start = owner.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={}).get_json()
        owner.client.post(
            f"/api/v1/public/responses/{start['response_id']}/answers",
            json={"answers": {survey["questions"][0]["id"]: "All good"}, "complete": True},
            headers={"X-Response-Token": start["response_token"]},
        )
    assert post.call_count == 1
    kwargs = post.call_args.kwargs
    body = kwargs["data"]
    event = json.loads(body)
    assert event["type"] == "response.completed"
    assert event["data"]["answers"][0]["value"] == "All good"
    ts, sig = (part.split("=", 1)[1] for part in kwargs["headers"]["X-SurveyAgent-Signature"].split(","))
    expected = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    assert sig == expected

    endpoint = owner.get("/api/v1/webhooks").get_json()["items"][0]
    assert endpoint["last_status"] == 200
    assert "secret" not in endpoint


def test_webhook_auto_disables_after_failures(owner):
    endpoint = owner.post("/api/v1/webhooks", json={"url": "https://hooks.example.com/x"}).get_json()
    with patch("survey_agent.services.webhooks.requests.post", return_value=MagicMock(status_code=500)):
        for _ in range(20):
            owner.post(f"/api/v1/webhooks/{endpoint['id']}/test")
    assert owner.get("/api/v1/webhooks").get_json()["items"][0]["active"] is False


def test_webhook_blocks_private_addresses_in_production(owner, app):
    app.config["APP_ENV"] = "production"
    res = owner.post("/api/v1/webhooks", json={"url": "http://127.0.0.1:8080/hook"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_webhook_url"


def test_webhooks_require_team_plan(app):
    api = register(app, plan="pro")
    assert api.post("/api/v1/webhooks", json={"url": "https://example.com/h"}).status_code == 402


def test_public_plans_endpoint(app):
    plans = ApiClient(app).get("/api/v1/public/plans").get_json()["plans"]
    assert plans[1]["id"] == "pro" and plans[1]["price_monthly"] == 39
