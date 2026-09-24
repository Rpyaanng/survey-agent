import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from survey_agent.extensions import db
from survey_agent.models import Outreach, Response

from .conftest import make_survey, register

SECRET = "whsec_test"


def _signed(payload: dict) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return body, {"elevenlabs-signature": f"t={ts},v0={sig}", "Content-Type": "application/json"}


def _voice_survey(owner):
    return make_survey(owner, settings={"modes": ["form", "chat", "voice"]})


def _start_voice(owner, survey):
    fake = MagicMock()
    fake.json.return_value = {"signed_url": "wss://api.elevenlabs.io/signed"}
    fake.raise_for_status.return_value = None
    with patch("survey_agent.services.voice.requests.get", return_value=fake):
        res = owner.client.post(
            f"/api/v1/public/surveys/{survey['public_token']}/responses",
            json={"channel": "voice", "respondent": {"name": "Lee"}},
        )
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def _post_call(owner, response_id, transcript, duration=95):
    body, headers = _signed({
        "type": "post_call_transcription",
        "data": {
            "conversation_id": "conv_1",
            "transcript": transcript,
            "metadata": {"call_duration_secs": duration},
            "conversation_initiation_client_data": {"dynamic_variables": {"response_id": response_id}},
        },
    })
    return owner.client.post("/api/v1/integrations/elevenlabs/post-call", data=body, headers=headers)


def test_browser_voice_session(owner):
    survey = _voice_survey(owner)
    session = _start_voice(owner, survey)
    assert session["signed_url"].startswith("wss://")
    variables = session["dynamic_variables"]
    assert variables["response_id"] == session["response_id"]
    assert "How did you hear about us?" in variables["questions"]
    assert "Options: Search | Friend | Social media" in variables["questions"]
    assert variables["respondent_name"] == "Lee"


def test_voice_requires_pro(app):
    api = register(app)
    survey = make_survey(api)
    res = api.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": "voice"})
    assert res.status_code in (400, 402)


def test_post_call_webhook_extracts_answers(owner):
    survey = _voice_survey(owner)
    session = _start_voice(owner, survey)
    transcript = [
        {"role": "agent", "message": "Hi! What is your name?"},
        {"role": "user", "message": "It's Jordan."},
        {"role": "agent", "message": "Great. How did you hear about us?"},
        {"role": "user", "message": "Honestly a friend mentioned it."},
        {"role": "agent", "message": "How satisfied are you? One to five."},
        {"role": "user", "message": "Probably a 4."},
    ]
    res = _post_call(owner, session["response_id"], transcript)
    assert res.status_code == 200
    assert res.get_json()["status"] == "queued"

    detail = owner.get(f"/api/v1/responses/{session['response_id']}").get_json()
    assert detail["status"] == "completed"
    values = sorted(str(a["value"]) for a in detail["answers"])
    assert values == ["4", "Friend", "It's Jordan."]
    assert detail["meta"]["call_duration_seconds"] == 95
    assert owner.get("/api/v1/billing").get_json()["usage"]["voice_minutes"]["used"] == 2

    # Retried webhooks are idempotent.
    assert _post_call(owner, session["response_id"], transcript).get_json()["status"] == "already_processed"


def test_post_call_rejects_bad_signature(owner):
    res = owner.client.post(
        "/api/v1/integrations/elevenlabs/post-call",
        data=b"{}",
        headers={"elevenlabs-signature": f"t={int(time.time())},v0=deadbeef"},
    )
    assert res.status_code == 401


def test_silent_call_is_abandoned(owner):
    survey = _voice_survey(owner)
    session = _start_voice(owner, survey)
    _post_call(owner, session["response_id"], [{"role": "agent", "message": "Hello? Anyone there?"}], duration=10)
    assert db.session.get(Response, session["response_id"]).status == "abandoned"


def test_outbound_phone_campaign(owner):
    survey = make_survey(owner)
    fake = MagicMock()
    fake.json.return_value = {"conversation_id": "conv_out"}
    fake.raise_for_status.return_value = None
    with patch("survey_agent.services.voice.requests.post", return_value=fake) as post:
        res = owner.post(
            f"/api/v1/surveys/{survey['id']}/outreach",
            json={"contacts": [{"name": "Ana", "phone": "+14035550100"}, {"name": "Dup", "phone": "+14035550100"}]},
        )
    assert res.status_code == 201, res.get_json()
    assert len(res.get_json()["items"]) == 1
    sent = post.call_args.kwargs["json"]
    assert sent["to_number"] == "+14035550100"
    response_id = sent["conversation_initiation_client_data"]["dynamic_variables"]["response_id"]

    outreach = db.session.query(Outreach).one()
    assert outreach.status == "calling"
    assert outreach.conversation_id == "conv_out"

    _post_call(owner, response_id, [
        {"role": "agent", "message": "What is your name?"},
        {"role": "user", "message": "Ana Lopez"},
    ])
    db.session.refresh(outreach)
    assert outreach.status == "completed"
    listing = owner.get(f"/api/v1/surveys/{survey['id']}/outreach").get_json()
    assert listing["items"][0]["status"] == "completed"


def test_outreach_validates_phone_numbers(owner):
    survey = make_survey(owner)
    res = owner.post(f"/api/v1/surveys/{survey['id']}/outreach", json={"contacts": [{"phone": "555-1234"}]})
    assert res.status_code == 422


def test_outreach_requires_team(app):
    api = register(app, plan="pro")
    survey = make_survey(api)
    res = api.post(f"/api/v1/surveys/{survey['id']}/outreach", json={"contacts": [{"phone": "+14035550100"}]})
    assert res.status_code == 402
