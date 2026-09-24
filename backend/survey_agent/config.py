"""Application configuration.

All settings come from environment variables so the same image runs in every
environment. ``Config.from_env()`` picks the class named by ``APP_ENV``.
"""
from __future__ import annotations

import os
from datetime import timedelta


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///survey_agent.db")
    # Render/Heroku hand out postgres:// URLs; SQLAlchemy 2 needs the explicit driver.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    APP_ENV = "development"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # PDF imports are capped at ~10 MB

    # URLs
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:5000")
    CORS_ORIGINS = _list("CORS_ORIGINS", "http://localhost:3000")

    # Auth
    SESSION_COOKIE_NAME = "sa_session"
    AUTH_TOKEN_TTL = timedelta(days=int(os.getenv("AUTH_TOKEN_TTL_DAYS", "7")))
    AUTH_COOKIE_SECURE = _bool("AUTH_COOKIE_SECURE", False)

    # Rate limiting (memory:// is per-process; use redis:// in production)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)
    RATELIMIT_HEADERS_ENABLED = True

    # Background work: "thread" runs tasks on a pool, "sync" runs inline (tests).
    TASK_BACKEND = os.getenv("TASK_BACKEND", "thread")

    # AI
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "fake")
    AI_MODEL = os.getenv("AI_MODEL", "claude-opus-5")
    AI_REFUSAL_FALLBACK = _bool("AI_REFUSAL_FALLBACK", True)

    # Voice (ElevenLabs Conversational AI)
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
    ELEVENLABS_PHONE_NUMBER_ID = os.getenv("ELEVENLABS_PHONE_NUMBER_ID", "")
    ELEVENLABS_WEBHOOK_SECRET = os.getenv("ELEVENLABS_WEBHOOK_SECRET", "")

    # Billing (Stripe)
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_TEAM = os.getenv("STRIPE_PRICE_TEAM", "")
    # Without Stripe keys, allow plan switching without payment (local/demo only).
    ALLOW_DEV_BILLING = _bool("ALLOW_DEV_BILLING", True)

    # Email (Resend). Without a key, emails are logged instead of sent.
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "Survey Agent <onboarding@resend.dev>")

    @staticmethod
    def from_env() -> type["Config"]:
        return {
            "production": ProductionConfig,
            "test": TestConfig,
        }.get(os.getenv("APP_ENV", "development"), Config)


class ProductionConfig(Config):
    APP_ENV = "production"
    AUTH_COOKIE_SECURE = _bool("AUTH_COOKIE_SECURE", True)
    ALLOW_DEV_BILLING = _bool("ALLOW_DEV_BILLING", False)


class TestConfig(Config):
    APP_ENV = "test"
    TESTING = True
    SECRET_KEY = "test-secret-key-that-is-long-enough-for-hs256"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    TASK_BACKEND = "sync"
    AI_PROVIDER = "fake"
    RATELIMIT_ENABLED = False
    ALLOW_DEV_BILLING = True
    STRIPE_SECRET_KEY = ""
    RESEND_API_KEY = ""
    ELEVENLABS_API_KEY = "test-key"
    ELEVENLABS_AGENT_ID = "agent_test"
    ELEVENLABS_PHONE_NUMBER_ID = "phone_test"
    ELEVENLABS_WEBHOOK_SECRET = "whsec_test"
