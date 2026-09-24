from survey_agent.extensions import db
from survey_agent.models import UsageEvent

from .conftest import make_survey, register


def _start(api, survey, channel="form"):
    res = api.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": channel})
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def _post(api, path, token, payload):
    return api.client.post(path, json=payload, headers={"X-Response-Token": token})


def test_public_view_hides_drafts(owner):
    draft = make_survey(owner, publish=False)
    assert owner.client.get(f"/api/v1/public/surveys/{draft['public_token']}").status_code == 404
    live = make_survey(owner)
    view = owner.client.get(f"/api/v1/public/surveys/{live['public_token']}").get_json()
    assert view["accepting_responses"] is True
    assert view["modes"] == ["form", "chat"]
    assert "org_id" not in view


def test_form_response_validation_and_completion(owner):
    survey = make_survey(owner)
    q = {item["title"]: item["id"] for item in survey["questions"]}
    start = _start(owner, survey)
    path = f"/api/v1/public/responses/{start['response_id']}/answers"

    bad = _post(owner, path, start["response_token"], {"answers": {q["How did you hear about us?"]: "Billboard"}})
    assert bad.status_code == 422
    assert q["How did you hear about us?"] in bad.get_json()["error"]["details"]

    missing = _post(owner, path, start["response_token"], {"answers": {q["What is your name?"]: "Ana"}, "complete": True})
    assert missing.status_code == 422
    assert missing.get_json()["error"]["details"][q["How did you hear about us?"]] == "This question is required"

    ok = _post(
        owner,
        path,
        start["response_token"],
        {
            "answers": {
                q["What is your name?"]: "Ana",
                q["How did you hear about us?"]: "friend",
                q["How satisfied are you?"]: 4,
                q["Would you buy again?"]: "yes",
            },
            "complete": True,
        },
    )
    assert ok.status_code == 200, ok.get_json()
    assert ok.get_json()["status"] == "completed"

    detail = owner.get(f"/api/v1/responses/{start['response_id']}").get_json()
    values = {a["question_id"]: a["value"] for a in detail["answers"]}
    assert values[q["How did you hear about us?"]] == "Friend"
    assert values[q["Would you buy again?"]] is True

    again = _post(owner, path, start["response_token"], {"answers": {}})
    assert again.status_code == 409


def test_wrong_token_rejected(owner):
    survey = make_survey(owner)
    start = _start(owner, survey)
    res = _post(owner, f"/api/v1/public/responses/{start['response_id']}/answers", "nope", {"answers": {}})
    assert res.status_code == 403


def test_chat_interview_end_to_end(owner):
    survey = make_survey(owner)
    start = _start(owner, survey, channel="chat")
    path = f"/api/v1/public/responses/{start['response_id']}/chat"
    token = start["response_token"]

    opening = _post(owner, path, token, {}).get_json()
    assert "What is your name?" in opening["reply"]
    assert opening["progress"] == {"answered": 0, "total": 5}

    turn = _post(owner, path, token, {"message": "I'm Priya"}).get_json()
    assert "How did you hear about us?" in turn["reply"]

    invalid = _post(owner, path, token, {"message": "a billboard"}).get_json()
    assert "didn't quite get that" in invalid["reply"]
    assert invalid["progress"]["answered"] == 1

    for message in ["A friend told me", "I'd say 5", "skip", "yes definitely"]:
        result = _post(owner, path, token, {"message": message}).get_json()
    assert result["completed"] is True
    assert result["progress"] == {"answered": 4, "total": 5}

    detail = owner.get(f"/api/v1/responses/{start['response_id']}").get_json()
    assert detail["status"] == "completed"
    assert detail["channel"] == "chat"
    assert len(detail["transcript"]) >= 12
    raw = {a["raw_text"] for a in detail["answers"]}
    assert "A friend told me" in raw


def test_chat_resume_replays_last_message(owner):
    survey = make_survey(owner)
    start = _start(owner, survey, channel="chat")
    path = f"/api/v1/public/responses/{start['response_id']}/chat"
    first = _post(owner, path, start["response_token"], {}).get_json()
    again = _post(owner, path, start["response_token"], {}).get_json()
    assert again["reply"] == first["reply"]


def test_disabled_mode_rejected(owner):
    survey = make_survey(owner, settings={"modes": ["form"]})
    res = owner.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": "chat"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "mode_disabled"


def test_response_limit_closes_survey(owner):
    survey = make_survey(owner, questions=[{"type": "short_text", "title": "Hi?"}], settings={"response_limit": 1})
    start = _start(owner, survey)
    qid = survey["questions"][0]["id"]
    _post(owner, f"/api/v1/public/responses/{start['response_id']}/answers", start["response_token"],
          {"answers": {qid: "hello"}, "complete": True})
    assert owner.get(f"/api/v1/surveys/{survey['id']}").get_json()["status"] == "closed"
    res = owner.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": "form"})
    assert res.status_code in (404, 410)


def test_monthly_response_quota(app):
    api = register(app)  # free: 100 responses / month
    survey = make_survey(api)
    db.session.add(UsageEvent(org_id=api.org_id, metric="responses", quantity=100))
    db.session.commit()
    res = api.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": "form"})
    assert res.status_code == 402
    assert res.get_json()["error"]["code"] == "plan_limit"


def test_status_polling(owner):
    survey = make_survey(owner)
    start = _start(owner, survey)
    res = owner.client.get(f"/api/v1/public/responses/{start['response_id']}", headers={"X-Response-Token": start["response_token"]})
    assert res.get_json()["status"] == "in_progress"
    assert owner.client.get(f"/api/v1/public/responses/{start['response_id']}").status_code == 404
