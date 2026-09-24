"""Surveys, questions, responses, answers and phone outreach."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils import iso, new_id, new_token, utcnow


class SurveyStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class QuestionType(StrEnum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    DROPDOWN = "dropdown"
    RATING = "rating"
    NPS = "nps"
    YES_NO = "yes_no"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    TIME = "time"

    @property
    def has_choices(self) -> bool:
        return self in {QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE, QuestionType.DROPDOWN}


class Channel(StrEnum):
    FORM = "form"
    CHAT = "chat"
    VOICE = "voice"
    PHONE = "phone"
    API = "api"


class ResponseStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"  # post-call transcript is being analysed
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class Survey(db.Model):
    __tablename__ = "surveys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("srv"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default=SurveyStatus.DRAFT.value, index=True)
    public_token: Mapped[str] = mapped_column(String(48), unique=True, default=lambda: new_token(12))
    settings: Mapped[dict] = mapped_column(db.JSON, default=dict)
    # Where the questions came from: {"type": "manual"|"ai"|"pdf"|"google_form", "url"?, "filename"?}
    source: Mapped[dict] = mapped_column(db.JSON, default=lambda: {"type": "manual"})
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    published_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]

    questions: Mapped[list["Question"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", order_by="Question.position"
    )

    @property
    def active_questions(self) -> list["Question"]:
        return [q for q in self.questions if not q.archived]

    def to_dict(self, *, include_questions: bool = True) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "public_token": self.public_token,
            "settings": self.settings or {},
            "source": self.source or {"type": "manual"},
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "published_at": iso(self.published_at),
            "closed_at": iso(self.closed_at),
            "question_count": len(self.active_questions),
        }
        if include_questions:
            data["questions"] = [q.to_dict() for q in self.active_questions]
        return data


class Question(db.Model):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("q"))
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    type: Mapped[str] = mapped_column(String(24), default=QuestionType.SHORT_TEXT.value)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    required: Mapped[bool] = mapped_column(default=False)
    # {"choices": [...], "allow_other": bool, "min": int, "max": int, "min_label": str, "max_label": str}
    options: Mapped[dict] = mapped_column(db.JSON, default=dict)
    # Questions removed after collecting answers are archived so history stays intact.
    archived: Mapped[bool] = mapped_column(default=False)

    survey: Mapped[Survey] = relationship(back_populates="questions")

    @property
    def qtype(self) -> QuestionType:
        return QuestionType(self.type)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": self.position,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "required": self.required,
            "options": self.options or {},
        }


class Response(db.Model):
    __tablename__ = "responses"
    __table_args__ = (Index("ix_responses_survey_status", "survey_id", "status"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("rsp"))
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default=Channel.FORM.value)
    status: Mapped[str] = mapped_column(String(16), default=ResponseStatus.IN_PROGRESS.value)
    # Respondents never log in; this hashed bearer token authorizes writes to their response.
    access_token_hash: Mapped[str] = mapped_column(String(64))
    respondent: Mapped[dict] = mapped_column(db.JSON, default=dict)
    transcript: Mapped[list] = mapped_column(db.JSON, default=list)
    meta: Mapped[dict] = mapped_column(db.JSON, default=dict)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    outreach_id: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None]

    survey: Mapped[Survey] = relationship()
    answers: Mapped[list["Answer"]] = relationship(back_populates="response", cascade="all, delete-orphan")

    def answers_by_question(self) -> dict[str, "Answer"]:
        return {a.question_id: a for a in self.answers}

    def to_dict(self, *, include_detail: bool = False) -> dict:
        data = {
            "id": self.id,
            "survey_id": self.survey_id,
            "channel": self.channel,
            "status": self.status,
            "respondent": self.respondent or {},
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
            "answer_count": len(self.answers),
        }
        if include_detail:
            data["answers"] = [a.to_dict() for a in self.answers]
            data["transcript"] = self.transcript or []
            data["meta"] = {k: v for k, v in (self.meta or {}).items() if not k.startswith("_")}
            data["error"] = self.error
        return data


class Answer(db.Model):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("response_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ans"))
    response_id: Mapped[str] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    # Normalized, type-checked value (str | list[str] | int | float | bool).
    value: Mapped[object] = mapped_column(db.JSON)
    # What the respondent actually said, for conversational channels.
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    response: Mapped[Response] = relationship(back_populates="answers")

    def to_dict(self) -> dict:
        return {"question_id": self.question_id, "value": self.value, "raw_text": self.raw_text}


class Outreach(db.Model):
    """An outbound phone interview placed by the voice agent."""

    __tablename__ = "outreach"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("out"))
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(32), index=True)
    # queued | calling | completed | failed
    status: Mapped[str] = mapped_column(String(16), default="queued")
    response_id: Mapped[str | None] = mapped_column(String(32))
    conversation_id: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "status": self.status,
            "response_id": self.response_id,
            "error": self.error,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
