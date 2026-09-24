"""Plan catalog: the single source of truth for pricing, quotas and features.

Stripe only knows about prices; everything the product enforces lives here.
``None`` as a limit means unlimited.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Feature flags gated by plan.
FEATURES = {
    "chat": "AI chat interviews",
    "ai_builder": "Generate surveys with AI",
    "import": "Import from PDF and Google Forms",
    "voice": "Browser voice interviews",
    "phone": "Outbound phone interviews",
    "export": "CSV / JSON export",
    "insights": "AI response insights",
    "remove_branding": "Remove Survey Agent branding",
    "api_access": "REST API keys",
    "webhooks": "Outbound webhooks",
}

# Metered quotas, reset each billing period.
METRICS = ("responses", "ai_generations", "voice_minutes")


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_monthly: int | None  # USD; None = contact sales
    tagline: str
    limits: dict[str, int | None]
    features: frozenset[str]
    purchasable: bool = True
    highlights: tuple[str, ...] = field(default_factory=tuple)

    def limit(self, key: str) -> int | None:
        return self.limits.get(key)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price_monthly": self.price_monthly,
            "tagline": self.tagline,
            "limits": self.limits,
            "features": sorted(self.features),
            "purchasable": self.purchasable,
            "highlights": list(self.highlights),
        }


_BASE = {"chat", "ai_builder"}
_PRO = _BASE | {"import", "voice", "export", "insights", "remove_branding"}
_TEAM = _PRO | {"phone", "api_access", "webhooks"}

PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_monthly=0,
        tagline="Try conversational surveys.",
        limits={
            "active_surveys": 3,
            "responses_per_month": 100,
            "seats": 1,
            "ai_generations_per_month": 10,
            "voice_minutes_per_month": 0,
        },
        features=frozenset(_BASE),
        purchasable=False,
        highlights=("3 live surveys", "100 responses / month", "Form + AI chat modes"),
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_monthly=39,
        tagline="For professionals running research every week.",
        limits={
            "active_surveys": None,
            "responses_per_month": 2_000,
            "seats": 3,
            "ai_generations_per_month": 200,
            "voice_minutes_per_month": 300,
        },
        features=frozenset(_PRO),
        highlights=(
            "Unlimited surveys",
            "2,000 responses / month",
            "Browser voice interviews (300 min)",
            "PDF & Google Forms import",
            "AI insights and CSV export",
        ),
    ),
    "team": Plan(
        id="team",
        name="Team",
        price_monthly=149,
        tagline="For teams that field studies at scale.",
        limits={
            "active_surveys": None,
            "responses_per_month": 10_000,
            "seats": 15,
            "ai_generations_per_month": 1_000,
            "voice_minutes_per_month": 2_000,
        },
        features=frozenset(_TEAM),
        highlights=(
            "Everything in Pro",
            "10,000 responses / month",
            "Outbound phone interviews (2,000 min)",
            "REST API and webhooks",
            "15 seats with roles",
        ),
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        price_monthly=None,
        tagline="Custom volume, SSO and data residency.",
        limits={
            "active_surveys": None,
            "responses_per_month": None,
            "seats": None,
            "ai_generations_per_month": None,
            "voice_minutes_per_month": None,
        },
        features=frozenset(FEATURES),
        purchasable=False,
        highlights=("Unlimited everything", "Dedicated support", "Custom contracts & DPA"),
    ),
}

# Cheapest plan that unlocks each feature, used in upgrade prompts.
FEATURE_MIN_PLAN = {
    feature: next(p.id for p in PLANS.values() if feature in p.features) for feature in FEATURES
}

METRIC_LIMIT_KEY = {
    "responses": "responses_per_month",
    "ai_generations": "ai_generations_per_month",
    "voice_minutes": "voice_minutes_per_month",
}


def get_plan(plan_id: str | None) -> Plan:
    return PLANS.get(plan_id or "free", PLANS["free"])
