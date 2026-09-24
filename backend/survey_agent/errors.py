"""Uniform JSON error responses.

Every error leaves the API as ``{"error": {"code", "message", "details"?}}`` so
the frontend can branch on ``code`` (e.g. ``plan_limit`` shows an upgrade CTA).
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status_code = status
        self.details = details

    def to_response(self):
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            body["details"] = self.details
        return jsonify({"error": body}), self.status_code


class NotFound(APIError):
    status_code = 404
    code = "not_found"

    def __init__(self, what: str = "Resource"):
        super().__init__(f"{what} not found")


class Unauthorized(APIError):
    status_code = 401
    code = "unauthorized"


class Forbidden(APIError):
    status_code = 403
    code = "forbidden"


class Conflict(APIError):
    status_code = 409
    code = "conflict"


class PlanLimitError(APIError):
    """Raised when an org hits a quota or lacks a feature on its current plan."""

    status_code = 402
    code = "plan_limit"

    def __init__(self, message: str, *, feature: str | None = None, required_plan: str | None = None):
        super().__init__(message, details={"feature": feature, "required_plan": required_plan})


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return err.to_response()

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in err.errors(include_url=False)
        ]
        return APIError("Invalid request", code="validation_error", status=422, details=details).to_response()

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        return jsonify({"error": {"code": code, "message": err.description}}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        logger.exception("Unhandled error")
        return jsonify({"error": {"code": "internal_error", "message": "Something went wrong"}}), 500
