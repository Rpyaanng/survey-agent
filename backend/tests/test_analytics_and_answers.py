import pytest

from survey_agent.models import Question
from survey_agent.services.answers import AnswerError, normalize_answer

from .conftest import make_survey

NPS_SURVEY = [
    {"type": "nps", "title": "Recommend?", "required": True},
    {"type": "multiple_choice", "title": "Features?", "options": {"choices": ["A", "B", "C"]}},
    {"type": "long_text", "title": "Comments?"},
    {"type": "number", "title": "Age?"},
]


def _complete(owner, survey, answers):
    start = owner.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={}).get_json()
    res = owner.client.post(
        f"/api/v1/public/responses/{start['response_id']}/answers",
        json={"answers": answers, "complete": True},
        headers={"X-Response-Token": start["response_token"]},
    )
    assert res.status_code == 200, res.get_json()


def test_analytics_and_nps(owner):
    survey = make_survey(owner, questions=NPS_SURVEY)
    q = [item["id"] for item in survey["questions"]]
    for score, feats, comment, age in [(10, ["A", "B"], "Love it", 30), (9, ["A"], "Great", 40), (3, ["C"], "Slow", 50), (7, [], "", 20)]:
        answers = {q[0]: score, q[3]: age}
        if feats:
            answers[q[1]] = feats
        if comment:
            answers[q[2]] = comment
        _complete(owner, survey, answers)
    owner.client.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={})  # abandoned start

    stats = owner.get(f"/api/v1/surveys/{survey['id']}/analytics").get_json()
    assert stats["summary"]["started"] == 5
    assert stats["summary"]["completed"] == 4
    assert stats["summary"]["completion_rate"] == 0.8
    nps = stats["questions"][0]
    assert nps["nps"] == {"score": 25, "promoters": 2, "passives": 1, "detractors": 1}
    features = {d["label"]: d["count"] for d in stats["questions"][1]["distribution"]}
    assert features == {"A": 2, "B": 1, "C": 1}
    assert stats["questions"][1]["skipped"] == 1
    assert set(stats["questions"][2]["samples"]) == {"Love it", "Great", "Slow"}
    assert stats["questions"][3]["average"] == 35
    assert sum(day["count"] for day in stats["timeline"]) == 4


def test_insights(owner):
    survey = make_survey(owner, questions=NPS_SURVEY)
    assert owner.post(f"/api/v1/surveys/{survey['id']}/insights").status_code == 400
    _complete(owner, survey, {survey["questions"][0]["id"]: 10})
    insights = owner.post(f"/api/v1/surveys/{survey['id']}/insights").get_json()
    assert insights["headline"]
    assert any(f["title"] == "Net Promoter Score" for f in insights["key_findings"])


def test_csv_export(owner):
    survey = make_survey(owner, questions=NPS_SURVEY)
    q = [item["id"] for item in survey["questions"]]
    _complete(owner, survey, {q[0]: 8, q[1]: ["A", "C"], q[2]: "=HYPERLINK(\"http://evil\")", q[3]: -5})
    res = owner.get(f"/api/v1/surveys/{survey['id']}/export?format=csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    text = res.get_data(as_text=True).lstrip("﻿")
    header, row = text.strip().splitlines()
    assert header.endswith("Recommend?,Features?,Comments?,Age?")
    assert "A, C" in row
    assert "'=HYPERLINK" in row  # formula injection neutralized
    assert row.endswith(",-5")


def test_json_export(owner):
    survey = make_survey(owner, questions=NPS_SURVEY)
    _complete(owner, survey, {survey["questions"][0]["id"]: 6})
    data = owner.get(f"/api/v1/surveys/{survey['id']}/export?format=json").get_json()
    assert data["responses"][0]["answers"][0] == {
        "question_id": survey["questions"][0]["id"], "question": "Recommend?", "type": "nps", "value": 6,
    }


def _q(qtype, **options):
    return Question(id="q_1", type=qtype, title="Q", options=options)


@pytest.mark.parametrize(
    ("qtype", "options", "value", "expected"),
    [
        ("short_text", {}, "  hello ", "hello"),
        ("single_choice", {"choices": ["Red", "Blue"]}, "blue", "Blue"),
        ("single_choice", {"choices": ["Red", "Blue"], "allow_other": True}, "Teal", "Teal"),
        ("dropdown", {"choices": ["Canada", "Mexico"]}, ["Canada"], "Canada"),
        ("multiple_choice", {"choices": ["Yes, weekly", "No", "Maybe"]}, "Yes, weekly", ["Yes, weekly"]),
        ("multiple_choice", {"choices": ["A", "B", "C"]}, "a | C", ["A", "C"]),
        ("multiple_choice", {"choices": ["A", "B", "C"]}, "A__B", ["A", "B"]),
        ("multiple_choice", {"choices": ["A", "B"]}, ["A", "A", "B"], ["A", "B"]),
        ("rating", {"min": 1, "max": 5}, "4", 4),
        ("rating", {"min": 1, "max": 5}, 3.0, 3),
        ("nps", {"min": 0, "max": 10}, "I'd say 9", 9),
        ("yes_no", {}, "Yeah", True),
        ("yes_no", {}, "no.", False),
        ("yes_no", {}, False, False),
        ("number", {}, "1,200", 1200),
        ("number", {}, "3.5", 3.5),
        ("email", {}, "Me@Example.com ", "me@example.com"),
        ("phone", {}, "+1 (403) 555-0100", "+1 (403) 555-0100"),
        ("date", {}, "August 30th, 1997", "1997-08-30"),
        ("date", {}, "2024-02-29", "2024-02-29"),
        ("time", {}, "2:30 pm", "14:30"),
        ("time", {}, "09:05", "09:05"),
    ],
)
def test_normalize_valid(qtype, options, value, expected):
    assert normalize_answer(_q(qtype, **options), value) == expected


@pytest.mark.parametrize(
    ("qtype", "options", "value"),
    [
        ("short_text", {}, "   "),
        ("single_choice", {"choices": ["Red", "Blue"]}, "Green"),
        ("single_choice", {"choices": ["Red", "Blue"]}, ["Red", "Blue"]),
        ("multiple_choice", {"choices": ["A", "B"]}, "A | Z"),
        ("rating", {"min": 1, "max": 5}, "7"),
        ("rating", {"min": 1, "max": 5}, "3.5"),
        ("nps", {"min": 0, "max": 10}, "great"),
        ("yes_no", {}, "perhaps"),
        ("number", {}, True),
        ("email", {}, "not-an-email"),
        ("date", {}, "next tuesday"),
        ("time", {}, "noonish"),
    ],
)
def test_normalize_invalid(qtype, options, value):
    with pytest.raises(AnswerError):
        normalize_answer(_q(qtype, **options), value)
