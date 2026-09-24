"""Survey analytics: funnel, channel mix, timeline and per-question aggregates."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from statistics import mean, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Question, QuestionType, Response, ResponseStatus, Survey
from ..utils import utcnow

TEXT_SAMPLE = 25


def _completed_responses(survey: Survey) -> list[Response]:
    return list(
        db.session.scalars(
            select(Response)
            .where(Response.survey_id == survey.id, Response.status == ResponseStatus.COMPLETED.value)
            .options(selectinload(Response.answers))
            .order_by(Response.completed_at.desc())
        )
    )


def _question_stats(question: Question, values: list[Any], completed: int) -> dict[str, Any]:
    qtype = question.qtype
    opts = question.options or {}
    stats: dict[str, Any] = {
        "question_id": question.id,
        "title": question.title,
        "type": question.type,
        "answered": len(values),
        "skipped": max(completed - len(values), 0),
    }
    if qtype.has_choices:
        counts: Counter[str] = Counter()
        for value in values:
            counts.update(value if isinstance(value, list) else [value])
        choices = opts.get("choices", [])
        other = sum(c for label, c in counts.items() if label not in choices)
        stats["distribution"] = [{"label": c, "count": counts.get(c, 0)} for c in choices]
        if other:
            stats["distribution"].append({"label": "Other", "count": other})
        if qtype == QuestionType.MULTIPLE_CHOICE:
            stats["note"] = "Respondents could select multiple options"
    elif qtype in (QuestionType.RATING, QuestionType.NPS):
        lo, hi = opts.get("min", 0), opts.get("max", 10)
        numbers = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        counts = Counter(numbers)
        stats["distribution"] = [{"label": str(n), "count": counts.get(n, 0)} for n in range(lo, hi + 1)]
        stats["average"] = round(mean(numbers), 2) if numbers else None
        if qtype == QuestionType.NPS and numbers:
            promoters = sum(1 for n in numbers if n >= 9)
            detractors = sum(1 for n in numbers if n <= 6)
            stats["nps"] = {
                "score": round((promoters - detractors) / len(numbers) * 100),
                "promoters": promoters,
                "passives": len(numbers) - promoters - detractors,
                "detractors": detractors,
            }
    elif qtype == QuestionType.YES_NO:
        yes = sum(1 for v in values if v is True)
        stats["distribution"] = [{"label": "Yes", "count": yes}, {"label": "No", "count": len(values) - yes}]
    elif qtype == QuestionType.NUMBER:
        numbers = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if numbers:
            stats.update(
                average=round(mean(numbers), 2), median=median(numbers), min=min(numbers), max=max(numbers)
            )
    else:
        stats["samples"] = [str(v) for v in values[:TEXT_SAMPLE]]
    return stats


def survey_analytics(survey: Survey) -> dict[str, Any]:
    all_responses = db.session.scalars(select(Response).where(Response.survey_id == survey.id)).all()
    completed = _completed_responses(survey)

    by_status = Counter(r.status for r in all_responses)
    by_channel = Counter(r.channel for r in completed)
    durations = [
        (r.completed_at - r.started_at).total_seconds() for r in completed if r.completed_at and r.started_at
    ]

    today = utcnow().date()
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    per_day = Counter(r.completed_at.date() for r in completed if r.completed_at)
    timeline = [{"date": d.isoformat(), "count": per_day.get(d, 0)} for d in days]

    answers_by_question: dict[str, list[Any]] = {}
    for response in completed:
        for answer in response.answers:
            answers_by_question.setdefault(answer.question_id, []).append(answer.value)

    started = len(all_responses)
    return {
        "summary": {
            "started": started,
            "completed": len(completed),
            "in_progress": by_status.get(ResponseStatus.IN_PROGRESS.value, 0),
            "completion_rate": round(len(completed) / started, 3) if started else None,
            "median_duration_seconds": round(median(durations)) if durations else None,
        },
        "channels": [{"channel": ch, "count": n} for ch, n in by_channel.most_common()],
        "timeline": timeline,
        "questions": [
            _question_stats(q, answers_by_question.get(q.id, []), len(completed)) for q in survey.active_questions
        ],
    }
