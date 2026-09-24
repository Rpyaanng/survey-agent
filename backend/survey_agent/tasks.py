"""Background task execution.

Slow side effects (webhooks, emails, transcript analysis, outbound calls) run
off the request thread. Tasks take IDs rather than ORM objects and reload
state, so any executor can run them. That keeps a move to a durable queue
(RQ/Celery) a change to this one module.

Backends (``TASK_BACKEND``):
* ``thread``: a bounded in-process pool (default).
* ``sync``: run inline, used by the test suite for determinism.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from flask import Flask, current_app

from .extensions import db

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tasks")
    return _executor


def _run(app: Flask, fn: Callable[..., Any], args: tuple, kwargs: dict) -> None:
    with app.app_context():
        try:
            fn(*args, **kwargs)
        except Exception:
            logger.exception("Background task %s failed", getattr(fn, "__name__", fn))
            db.session.rollback()
        finally:
            db.session.remove()


def enqueue(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run ``fn(*args, **kwargs)`` in the background with an app context."""
    if current_app.config.get("TASK_BACKEND") == "sync":
        try:
            fn(*args, **kwargs)
        except Exception:
            logger.exception("Task %s failed", getattr(fn, "__name__", fn))
            db.session.rollback()
        return
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    _get_executor().submit(_run, app, fn, args, kwargs)
