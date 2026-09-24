"""Request payload schemas. Validation errors become 422 ``validation_error`` responses."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

from .models import Channel, QuestionType, Role


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --------------------------------------------------------------------- auth
class RegisterIn(_In):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)
    organization_name: str = Field(default="", max_length=120)


class LoginIn(_In):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateIn(_In):
    name: str | None = Field(default=None, max_length=120)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


# ------------------------------------------------------------ organizations
class OrgCreateIn(_In):
    name: str = Field(min_length=1, max_length=120)


class BrandingIn(_In):
    logo_url: HttpUrl | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class OrgUpdateIn(_In):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    branding: BrandingIn | None = None


class InviteIn(_In):
    email: EmailStr
    role: Literal["admin", "editor", "viewer"] = "editor"


class MemberUpdateIn(_In):
    role: Literal["owner", "admin", "editor", "viewer"]


# ------------------------------------------------------------------ surveys
class QuestionOptions(_In):
    choices: list[str] = Field(default_factory=list, max_length=50)
    allow_other: bool = False
    min: int | None = None
    max: int | None = None
    min_label: str = Field(default="", max_length=60)
    max_label: str = Field(default="", max_length=60)

    @field_validator("choices")
    @classmethod
    def _clean_choices(cls, choices: list[str]) -> list[str]:
        seen: list[str] = []
        for choice in choices:
            choice = str(choice).strip()[:200]
            if choice and choice.lower() not in {c.lower() for c in seen}:
                seen.append(choice)
        return seen


class QuestionIn(_In):
    id: str | None = None  # present when updating an existing question
    type: QuestionType = QuestionType.SHORT_TEXT
    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=2000)
    required: bool = False
    options: QuestionOptions = Field(default_factory=QuestionOptions)

    @model_validator(mode="after")
    def _check_options(self) -> "QuestionIn":
        opts = self.options
        if self.type.has_choices:
            if len(opts.choices) < 2:
                raise ValueError(f"'{self.title[:40]}' needs at least two choices")
        else:
            opts.choices = []
            opts.allow_other = False
        if self.type == QuestionType.RATING:
            opts.min = 1 if opts.min is None else opts.min
            opts.max = 5 if opts.max is None else opts.max
            if not (0 <= opts.min < opts.max <= 10):
                raise ValueError("Rating scales must satisfy 0 <= min < max <= 10")
        elif self.type == QuestionType.NPS:
            opts.min, opts.max = 0, 10
            opts.min_label = opts.min_label or "Not at all likely"
            opts.max_label = opts.max_label or "Extremely likely"
        else:
            opts.min = opts.max = None
        return self

    def options_dict(self) -> dict[str, Any]:
        return self.options.model_dump(exclude_defaults=True)


class AgentSettings(_In):
    name: str = Field(default="Ava", max_length=40)
    tone: Literal["friendly", "professional", "playful", "empathetic", "concise"] = "friendly"
    instructions: str = Field(default="", max_length=2000)


class CollectSettings(_In):
    name: bool = False
    email: bool = False


class SurveySettings(_In):
    modes: list[Literal["form", "chat", "voice"]] = Field(default_factory=lambda: ["form", "chat"])
    welcome_message: str = Field(default="", max_length=2000)
    closing_message: str = Field(default="Thanks for taking the time to share your thoughts!", max_length=2000)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    collect: CollectSettings = Field(default_factory=CollectSettings)
    response_limit: int | None = Field(default=None, ge=1)
    notify_emails: list[EmailStr] = Field(default_factory=list, max_length=10)
    show_branding: bool = True
    language: str = Field(default="en", max_length=12)

    @field_validator("modes")
    @classmethod
    def _dedupe_modes(cls, modes: list[str]) -> list[str]:
        modes = list(dict.fromkeys(modes))
        if not modes:
            raise ValueError("Enable at least one response mode")
        return modes


class SurveyCreateIn(_In):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=200)
    settings: SurveySettings | None = None


class SurveyUpdateIn(_In):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    settings: SurveySettings | None = None


class QuestionsReplaceIn(_In):
    questions: list[QuestionIn] = Field(max_length=200)


class GenerateSurveyIn(_In):
    prompt: str = Field(min_length=10, max_length=4000)
    question_count: int = Field(default=8, ge=3, le=30)


class ImportGoogleFormIn(_In):
    url: HttpUrl


class OutreachIn(_In):
    class Contact(_In):
        name: str = Field(default="", max_length=120)
        phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", description="E.164 phone number")

    contacts: list[Contact] = Field(min_length=1, max_length=500)


# ------------------------------------------------------------- respondents
class StartResponseIn(_In):
    channel: Literal["form", "chat", "voice"] = "form"
    respondent: dict[str, str] = Field(default_factory=dict)

    @field_validator("respondent")
    @classmethod
    def _limit_respondent(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"name", "email", "phone"}
        return {k: str(v)[:200] for k, v in value.items() if k in allowed and v}

    @property
    def channel_enum(self) -> Channel:
        return Channel(self.channel)


class SubmitAnswersIn(_In):
    answers: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False


class ChatTurnIn(_In):
    message: str | None = Field(default=None, max_length=2000)


# ------------------------------------------------------------ billing / dev
class CheckoutIn(_In):
    plan: Literal["pro", "team"]


class ApiKeyIn(_In):
    name: str = Field(min_length=1, max_length=120)


WEBHOOK_EVENTS = ("response.completed", "survey.published", "survey.closed")


class WebhookIn(_In):
    url: HttpUrl
    events: list[Literal["response.completed", "survey.published", "survey.closed"]] = Field(
        default_factory=lambda: ["response.completed"], min_length=1
    )
    active: bool = True


class WebhookUpdateIn(_In):
    url: HttpUrl | None = None
    events: list[Literal["response.completed", "survey.published", "survey.closed"]] | None = None
    active: bool | None = None


ROLE_VALUES = [r.value for r in Role]
