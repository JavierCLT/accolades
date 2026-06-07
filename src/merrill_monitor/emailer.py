from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
from email.message import EmailMessage

from .utils import coerce_bool


LOGGER = logging.getLogger(__name__)


class EmailConfigError(RuntimeError):
    pass


def send_email(
    *,
    subject: str,
    body: str,
    sender: str,
    recipients: list[str],
    backend: str,
) -> None:
    if not sender:
        raise EmailConfigError("EMAIL_FROM is required")
    if not recipients:
        raise EmailConfigError("EMAIL_TO is required")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    if backend == "smtp":
        send_via_smtp(message)
    elif backend == "gmail_api":
        send_via_gmail_api(message)
    else:
        raise EmailConfigError("EMAIL_BACKEND must be 'smtp' or 'gmail_api'")


def send_via_smtp(message: EmailMessage) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_starttls = coerce_bool(os.getenv("SMTP_STARTTLS"), default=True)

    if not host:
        raise EmailConfigError("SMTP_HOST is required when EMAIL_BACKEND=smtp")

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        if use_starttls:
            server.starttls()
            server.ehlo()
        if username:
            if not password:
                raise EmailConfigError("SMTP_PASSWORD is required when SMTP_USERNAME is set")
            server.login(username, password)
        server.send_message(message)
    LOGGER.info("Email sent via SMTP to %s", message["To"])


def send_via_gmail_api(message: EmailMessage) -> None:
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if not token_json:
        raise EmailConfigError("GMAIL_TOKEN_JSON is required when EMAIL_BACKEND=gmail_api")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise EmailConfigError("google-api-python-client and google-auth are required for Gmail API") from exc

    info = json.loads(token_json)
    credentials = Credentials.from_authorized_user_info(info)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    LOGGER.info("Email sent via Gmail API to %s", message["To"])
