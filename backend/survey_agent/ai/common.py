from __future__ import annotations

from ..models import Question, QuestionType

TONE_GUIDE = {
    "friendly": "warm, upbeat and approachable",
    "professional": "polished, courteous and efficient",
    "playful": "light-hearted and fun while still respectful",
    "empathetic": "gentle, patient and reassuring; suited to sensitive topics",
    "concise": "brief and to the point, with minimal small talk",
}


def describe_question(question: Question, index: int, *, include_id: bool = True) -> str:
    """One-line description of a question for interviewer prompts."""
    qtype = question.qtype
    opts = question.options or {}
    head = f"{index}. "
    if include_id:
        head += f"[question_id: {question.id}] "
    flags = qtype.value + (", required" if question.required else ", optional")
    line = f"{head}({flags}) {question.title}"
    if question.description:
        line += f"\n   Context: {question.description}"
    if qtype.has_choices:
        line += "\n   Options: " + " | ".join(opts.get("choices", []))
        if opts.get("allow_other"):
            line += " | (other answers allowed)"
    elif qtype in (QuestionType.RATING, QuestionType.NPS):
        lo, hi = opts.get("min", 0), opts.get("max", 10)
        labels = ""
        if opts.get("min_label") or opts.get("max_label"):
            labels = f" ({lo} = {opts.get('min_label', '')}, {hi} = {opts.get('max_label', '')})"
        line += f"\n   Scale: {lo} to {hi}{labels}"
    return line


def describe_questions(questions: list[Question], *, include_id: bool = True) -> str:
    return "\n".join(describe_question(q, i, include_id=include_id) for i, q in enumerate(questions, 1))
