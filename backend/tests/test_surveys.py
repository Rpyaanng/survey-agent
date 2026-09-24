import io
from unittest.mock import patch

import pymupdf

from survey_agent.services.importers.google_forms import parse_form

from .conftest import SAMPLE_QUESTIONS, make_survey, register


def test_create_and_fetch_survey(owner):
    survey = make_survey(owner, publish=False)
    assert survey["status"] == "draft"
    assert [q["type"] for q in survey["questions"]] == [q["type"] for q in SAMPLE_QUESTIONS]
    detail = owner.get(f"/api/v1/surveys/{survey['id']}").get_json()
    assert detail["settings"]["modes"] == ["form", "chat"]
    assert detail["responses"]["total"] == 0
    assert detail["questions"][2]["options"] == {"min": 1, "max": 5}


def test_question_validation(owner):
    res = owner.post(
        "/api/v1/surveys",
        json={"title": "Bad", "questions": [{"type": "single_choice", "title": "Pick", "options": {"choices": ["Only"]}}]},
    )
    assert res.status_code == 422
    res = owner.post(
        "/api/v1/surveys",
        json={"title": "Bad", "questions": [{"type": "rating", "title": "Rate", "options": {"min": 5, "max": 2}}]},
    )
    assert res.status_code == 422


def test_publish_requires_questions(owner):
    survey = owner.post("/api/v1/surveys", json={"title": "Empty"}).get_json()
    res = owner.post(f"/api/v1/surveys/{survey['id']}/publish")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "no_questions"


def test_free_plan_active_survey_limit(app):
    api = register(app)  # free: 3 live surveys
    for _ in range(3):
        make_survey(api)
    draft = make_survey(api, publish=False)
    res = api.post(f"/api/v1/surveys/{draft['id']}/publish")
    assert res.status_code == 402
    assert res.get_json()["error"]["details"]["required_plan"] == "pro"


def test_replace_questions_archives_answered(owner):
    survey = make_survey(owner)
    q_name, q_source = survey["questions"][0], survey["questions"][1]
    start = owner.post(f"/api/v1/public/surveys/{survey['public_token']}/responses", json={"channel": "form"}).get_json()
    owner.post(
        f"/api/v1/public/responses/{start['response_id']}/answers",
        json={"answers": {q_name["id"]: "Sam"}},
        headers={"X-Response-Token": start["response_token"]},
    )
    # Keep only the source question (edited) and add a new one.
    res = owner.put(
        f"/api/v1/surveys/{survey['id']}/questions",
        json={
            "questions": [
                {**q_source, "title": "Where did you find us?"},
                {"type": "email", "title": "Your email?"},
            ]
        },
    )
    assert res.status_code == 200
    questions = res.get_json()["questions"]
    assert [q["title"] for q in questions] == ["Where did you find us?", "Your email?"]
    assert questions[0]["id"] == q_source["id"]
    # The answered question was archived, not deleted, so the response keeps its answer.
    response = owner.get(f"/api/v1/responses/{start['response_id']}").get_json()
    assert response["answers"][0]["question_id"] == q_name["id"]


def test_duplicate_and_delete(owner):
    survey = make_survey(owner)
    copy = owner.post(f"/api/v1/surveys/{survey['id']}/duplicate").get_json()
    assert copy["title"].endswith("(copy)")
    assert copy["status"] == "draft"
    assert len(copy["questions"]) == len(survey["questions"])
    assert owner.delete(f"/api/v1/surveys/{survey['id']}").status_code == 204
    assert owner.get(f"/api/v1/surveys/{survey['id']}").status_code == 404


def test_list_search_and_filter(owner):
    make_survey(owner)
    owner.post("/api/v1/surveys", json={"title": "Employee engagement"})
    listing = owner.get("/api/v1/surveys?q=employee").get_json()
    assert listing["total"] == 1
    assert owner.get("/api/v1/surveys?status=published").get_json()["total"] == 1


def test_generate_with_ai(owner):
    res = owner.post("/api/v1/surveys/generate", json={"prompt": "Feedback on our new onboarding flow", "question_count": 5})
    assert res.status_code == 201
    survey = res.get_json()
    assert survey["source"]["type"] == "ai"
    assert len(survey["questions"]) == 5
    billing = owner.get("/api/v1/billing").get_json()
    assert billing["usage"]["ai_generations"]["used"] == 1


def test_voice_mode_requires_plan(app):
    api = register(app)
    survey = make_survey(api, publish=False)
    res = api.patch(f"/api/v1/surveys/{survey['id']}", json={"settings": {"modes": ["form", "voice"]}})
    assert res.status_code == 402


GOOGLE_FORM_JSON = [
    None,
    [
        "Tell us about your visit",
        [
            [111, "Welcome!", "Intro text", 6, None],
            [222, "Your name", None, 0, [[1001, None, 1]]],
            [333, "Favourite colour", None, 2, [[1002, [["Red"], ["Blue"], ["Green"]], 0]]],
            [444, "Toppings", None, 4, [[1003, [["Cheese"], ["Olives"]], 0]]],
            [555, "Rate us", None, 5, [[1004, [["1"], ["2"], ["3"], ["4"], ["5"]], 0, ["Bad", "Great"]]]],
            [666, "Visit date", None, 9, [[1005, None, 0]]],
            [777, "Grid", None, 7, [[1006, None, 0]]],
        ],
        None, None, None, None, None, None,
        "Visit feedback",
        None,
        [None, None, None, None, None, None, 3],
    ],
    "/forms/doc",
    "Visit feedback form",
]


def test_parse_google_form():
    parsed = parse_form(GOOGLE_FORM_JSON)
    assert parsed["title"] == "Visit feedback"
    types = [(q["title"], q["type"]) for q in parsed["questions"]]
    assert types == [
        ("Email address", "email"),
        ("Your name", "short_text"),
        ("Favourite colour", "single_choice"),
        ("Toppings", "multiple_choice"),
        ("Rate us", "rating"),
        ("Visit date", "date"),
    ]
    rating = parsed["questions"][4]
    assert rating["options"] == {"min": 1, "max": 5, "min_label": "Bad", "max_label": "Great"}
    assert parsed["questions"][1]["required"] is True


def test_import_google_form_endpoint(owner):
    with patch(
        "survey_agent.services.importers.google_forms._fetch_form_json",
        return_value=(GOOGLE_FORM_JSON, "https://docs.google.com/forms/d/e/abc/viewform"),
    ):
        res = owner.post("/api/v1/surveys/import/google-form", json={"url": "https://docs.google.com/forms/d/e/abc/viewform"})
    assert res.status_code == 201, res.get_json()
    survey = res.get_json()
    assert survey["source"] == {"type": "google_form", "url": "https://docs.google.com/forms/d/e/abc/viewform"}
    assert len(survey["questions"]) == 6


def test_import_google_form_rejects_other_hosts(owner):
    res = owner.post("/api/v1/surveys/import/google-form", json={"url": "http://169.254.169.254/latest/meta-data"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_form_url"


def test_import_requires_pro(app):
    api = register(app)
    res = api.post("/api/v1/surveys/import/google-form", json={"url": "https://docs.google.com/forms/d/x/viewform"})
    assert res.status_code == 402


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Membership Application")
    page.insert_text((72, 110), "Full name:")
    page.insert_text((72, 140), "Do you have any dietary requirements?")
    data = doc.tobytes()
    doc.close()
    return data


def test_import_pdf(owner):
    res = owner.client.post(
        "/api/v1/surveys/import/pdf",
        data={"file": (io.BytesIO(_pdf_bytes()), "membership_form.pdf")},
        headers={"X-Requested-With": "fetch", "X-Org-Id": owner.org_id},
        content_type="multipart/form-data",
    )
    assert res.status_code == 201, res.get_json()
    survey = res.get_json()
    assert survey["source"] == {"type": "pdf", "filename": "membership_form.pdf"}
    titles = [q["title"] for q in survey["questions"]]
    assert "Full name" in titles
    assert "Do you have any dietary requirements?" in titles


def test_import_rejects_non_pdf(owner):
    res = owner.client.post(
        "/api/v1/surveys/import/pdf",
        data={"file": (io.BytesIO(b"not a pdf"), "x.pdf")},
        headers={"X-Requested-With": "fetch", "X-Org-Id": owner.org_id},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_pdf"
