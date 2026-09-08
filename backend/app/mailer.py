"""Thin SMTP wrapper used to actually deliver a report email once the user
has reviewed and approved the draft in the UI (human-in-the-loop). All
config comes from environment variables (see app.config / .env.example); if
SMTP isn't configured, send_email raises MailNotConfigured so the API can
tell the user plainly instead of failing obscurely.
"""
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)

_XLSX_MIME = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")


class MailNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(SMTP_HOST and (SMTP_FROM or SMTP_USERNAME))


def send_email(
    to_addrs: list[str],
    subject: str,
    body: str,
    attachment: Optional[tuple[str, bytes]] = None,
) -> None:
    if not is_configured():
        raise MailNotConfigured(
            "Email is not configured on this server. Set SMTP_HOST, SMTP_FROM "
            "(and SMTP_USERNAME / SMTP_PASSWORD if your provider requires auth) "
            "in .env and restart the backend."
        )
    if not to_addrs:
        raise ValueError("At least one recipient is required.")

    msg = EmailMessage()
    msg["From"] = SMTP_FROM or SMTP_USERNAME
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body or "")

    if attachment is not None:
        name, data = attachment
        msg.add_attachment(data, maintype=_XLSX_MIME[0], subtype=_XLSX_MIME[1], filename=name)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        if SMTP_USE_TLS:
            server.starttls(context=context)
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
