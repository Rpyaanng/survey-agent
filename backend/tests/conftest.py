from __future__ import annotations

import itertools

import pytest

from survey_agent import create_app
from survey_agent.config import TestConfig
from survey_agent.extensions import db
from survey_agent.models import Organization, Subscription

_counter = itertools.count()


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


class ApiClient:
    """Test client that behaves like the browser frontend (cookie session + CSRF header)."""

    def __init__(self, app, org_id: str | None = None):
        self.client = app.test_client()
        self.org_id = org_id
        self.user: dict | None = None

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"X-Requested-With": "fetch"}
        if self.org_id:
            headers["X-Org-Id"] = self.org_id
        headers.update(extra or {})
        return headers

    def get(self, url, **kw):
        return self.client.get(url, headers=self._headers(kw.pop("headers", None)), **kw)

    def post(self, url, json=None, **kw):
        return self.client.post(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def patch(self, url, json=None, **kw):
        return self.client.patch(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def put(self, url, json=None, **kw):
        return self.client.put(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self._headers(kw.pop("headers", None)), **kw)


def register(app, *, plan: str = "free", email: str | None = None) -> ApiClient:
    api = ApiClient(app)
    email = email or f"user{next(_counter)}@example.com"
    res = api.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Test"})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    api.user = body["user"]
    api.org_id = body["default_org_id"]
    if plan != "free":
        set_plan(api.org_id, plan)
    return api


def set_plan(org_id: str, plan: str) -> None:
    org = db.session.get(Organization, org_id)
    if org.subscription is None:
        org.subscription = Subscription()
    org.subscription.plan = plan
    org.subscription.status = "active"
    db.session.commit()


SAMPLE_QUESTIONS = [
    {"type": "short_text", "title": "What is your name?", "required": True},
    {
        "type": "single_choice",
        "title": "How did you hear about us?",
        "required": True,
        "options": {"choices": ["Search", "Friend", "Social media"]},
    },
    {"type": "rating", "title": "How satisfied are you?", "options": {"min": 1, "max": 5}},
    {"type": "nps", "title": "How likely are you to recommend us?"},
    {"type": "yes_no", "title": "Would you buy again?"},
]


def make_survey(api: ApiClient, *, publish: bool = True, questions=None, settings=None) -> dict:
    payload = {"title": "Customer survey", "questions": questions or SAMPLE_QUESTIONS}
    if settings:
        payload["settings"] = settings
    res = api.post("/api/v1/surveys", json=payload)
    assert res.status_code == 201, res.get_json()
    survey = res.get_json()
    if publish:
        res = api.post(f"/api/v1/surveys/{survey['id']}/publish")
        assert res.status_code == 200, res.get_json()
        survey = res.get_json()
    return survey


@pytest.fixture()
def owner(app) -> ApiClient:
    return register(app, plan="team")
