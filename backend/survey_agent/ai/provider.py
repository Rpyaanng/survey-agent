"""LLM provider abstraction.

Every AI feature calls ``get_provider().generate_json(...)`` with a JSON schema
and gets back a dict that matches it. Two implementations exist:

* ``AnthropicProvider`` calls Claude with structured outputs
  (``output_config.format``), so responses always parse.
* ``FakeProvider`` is a deterministic, rule-based engine. It's used in tests
  and whenever no ``ANTHROPIC_API_KEY`` is set, so the whole product runs
  offline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from flask import current_app

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class AIError(RuntimeError):
    pass


def load_prompt(name: str, **variables: str) -> str:
    text = (PROMPT_DIR / name).read_text(encoding="utf-8")
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    return text


class AIProvider(Protocol):
    name: str

    def generate_json(
        self,
        *,
        task: str,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        effort: str = "medium",
        max_tokens: int = 16000,
        hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, refusal_fallback: bool = True):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)
        self.model = model
        self.refusal_fallback = refusal_fallback

    def generate_json(self, *, task, system, messages, schema, effort="medium", max_tokens=16000, hint=None):
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }
        anthropic = self._anthropic
        try:
            if self.refusal_fallback:
                # Server-side fallback reroutes the rare safety decline to another model in the same call.
                response = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
                )
            else:
                response = self.client.messages.create(**params)
        except anthropic.RateLimitError as exc:
            raise AIError("The AI service is busy, please retry shortly") from exc
        except anthropic.APIStatusError as exc:
            logger.error("Anthropic API error on %s (%s): %s", task, exc.status_code, exc.message)
            raise AIError("The AI service returned an error") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError("Could not reach the AI service") from exc

        if response.stop_reason == "refusal":
            raise AIError("The AI declined to process this request")
        if response.stop_reason == "max_tokens":
            raise AIError("The AI response was cut off; try a smaller request")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Unparseable structured output for %s: %.500s", task, text)
            raise AIError("The AI returned an invalid response") from exc


def get_provider() -> AIProvider:
    cfg = current_app.config
    if cfg.get("AI_PROVIDER") == "anthropic" and cfg.get("ANTHROPIC_API_KEY"):
        cached = current_app.extensions.get("ai_provider")
        if cached is None:
            cached = AnthropicProvider(cfg["ANTHROPIC_API_KEY"], cfg["AI_MODEL"], cfg["AI_REFUSAL_FALLBACK"])
            current_app.extensions["ai_provider"] = cached
        return cached
    from .fake import FakeProvider

    return FakeProvider()
