from survey_agent.extensions import db
from survey_agent.models import Membership, Role

from .conftest import ApiClient, make_survey, register


def test_register_login_and_me(app):
    api = register(app, email="alice@example.com")
    me = api.get("/api/v1/auth/me").get_json()
    assert me["user"]["email"] == "alice@example.com"
    assert me["organizations"][0]["role"] == "owner"
    assert me["organizations"][0]["plan"] == "free"

    fresh = ApiClient(app)
    bad = fresh.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401
    assert bad.get_json()["error"]["code"] == "invalid_credentials"
    ok = fresh.post("/api/v1/auth/login", json={"email": "ALICE@example.com", "password": "password123"})
    assert ok.status_code == 200
    assert fresh.get("/api/v1/auth/me").status_code == 200


def test_duplicate_email_rejected(app):
    register(app, email="dup@example.com")
    res = ApiClient(app).post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert res.status_code == 409


def test_validation_errors_are_structured(app):
    res = ApiClient(app).post("/api/v1/auth/register", json={"email": "not-an-email", "password": "short"})
    assert res.status_code == 422
    fields = {d["field"] for d in res.get_json()["error"]["details"]}
    assert {"email", "password"} <= fields


def test_cookie_requests_require_csrf_header(app):
    api = register(app)
    res = api.client.post("/api/v1/surveys", json={"title": "x"}, headers={"X-Org-Id": api.org_id})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "csrf_failed"


def test_bearer_token_auth(app):
    client = app.test_client()
    res = client.post("/api/v1/auth/register", json={"email": "bearer@example.com", "password": "password123"})
    token = res.get_json()["token"]
    client.delete_cookie("sa_session")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


def test_unauthenticated(app):
    assert ApiClient(app).get("/api/v1/surveys").status_code == 401


def test_tenant_isolation(app):
    alice = register(app, plan="team")
    bob = register(app, plan="team")
    survey = make_survey(alice)
    assert bob.get(f"/api/v1/surveys/{survey['id']}").status_code == 404
    assert bob.delete(f"/api/v1/surveys/{survey['id']}").status_code == 404
    assert bob.get(f"/api/v1/surveys/{survey['id']}/responses").status_code == 404
    assert bob.get("/api/v1/surveys").get_json()["total"] == 0
    # Bob can't select Alice's org via the header either.
    bob.org_id = alice.org_id
    assert bob.get("/api/v1/surveys").status_code == 403


def test_viewer_cannot_edit(app):
    owner = register(app, plan="team")
    viewer = register(app)
    db.session.add(Membership(org_id=owner.org_id, user_id=viewer.user["id"], role=Role.VIEWER.value))
    db.session.commit()
    viewer.org_id = owner.org_id
    assert viewer.get("/api/v1/surveys").status_code == 200
    res = viewer.post("/api/v1/surveys", json={"title": "Nope"})
    assert res.status_code == 403


def test_invitation_flow_and_seat_limit(app):
    owner = register(app, plan="pro")  # 3 seats
    res = owner.post("/api/v1/org/invitations", json={"email": "new@example.com", "role": "editor"})
    assert res.status_code == 201
    token = res.get_json()["accept_link"].rsplit("/", 1)[1]

    info = ApiClient(app).get(f"/api/v1/invitations/{token}").get_json()
    assert info["email"] == "new@example.com"

    invitee = register(app, email="new@example.com")
    accepted = invitee.post(f"/api/v1/invitations/{token}/accept")
    assert accepted.status_code == 200
    assert accepted.get_json()["role"] == "editor"

    members = owner.get("/api/v1/org/members").get_json()["members"]
    assert len(members) == 2
    assert owner.post("/api/v1/org/invitations", json={"email": "c@example.com"}).status_code == 201
    over = owner.post("/api/v1/org/invitations", json={"email": "d@example.com"})
    assert over.status_code == 402
    assert over.get_json()["error"]["code"] == "plan_limit"


def test_invitation_email_must_match(app):
    owner = register(app, plan="pro")
    token = owner.post("/api/v1/org/invitations", json={"email": "right@example.com"}).get_json()["accept_link"].rsplit("/", 1)[1]
    wrong = register(app, email="wrong@example.com")
    assert wrong.post(f"/api/v1/invitations/{token}/accept").status_code == 403


def test_last_owner_cannot_be_demoted(app):
    owner = register(app)
    members = owner.get("/api/v1/org/members").get_json()["members"]
    res = owner.patch(f"/api/v1/org/members/{members[0]['id']}", json={"role": "editor"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "last_owner"
