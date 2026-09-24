from __future__ import annotations

import html
import logging

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to: str | list[str], subject: str, html_body: str) -> bool:
    """Send via Resend when configured; otherwise log so local dev stays quiet."""
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        return False
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        logger.info("[email disabled] to=%s subject=%s", recipients, subject)
        return False
    import resend

    resend.api_key = api_key
    try:
        resend.Emails.send(
            {"from": current_app.config["EMAIL_FROM"], "to": recipients, "subject": subject, "html": html_body}
        )
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipients)
        return False


def render_email(title: str, paragraphs: list[str], cta: tuple[str, str] | None = None) -> str:
    body = "".join(f"<p style='margin:0 0 14px;line-height:1.6'>{html.escape(p)}</p>" for p in paragraphs)
    button = ""
    if cta:
        label, url = cta
        button = (
            f"<a href='{html.escape(url)}' style='display:inline-block;padding:10px 18px;border-radius:8px;"
            f"background:#2563eb;color:#fff;text-decoration:none;font-weight:600'>{html.escape(label)}</a>"
        )
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#0f172a'>"
        f"<h2 style='margin:0 0 16px'>{html.escape(title)}</h2>{body}{button}"
        "<p style='margin-top:28px;color:#64748b;font-size:12px'>Sent by Survey Agent</p></div>"
    )
