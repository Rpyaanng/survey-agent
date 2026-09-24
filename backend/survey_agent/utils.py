from __future__ import annotations

import hashlib
import re
import secrets
import string
from datetime import UTC, datetime

_ALPHABET = string.ascii_letters + string.digits


def utcnow() -> datetime:
    """Naive UTC timestamp. Stored naive so SQLite and Postgres behave the same."""
    return datetime.now(UTC).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def new_id(prefix: str, length: int = 18) -> str:
    return f"{prefix}_" + "".join(secrets.choice(_ALPHABET) for _ in range(length))


def new_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def slugify(value: str, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_length].strip("-") or "org"
