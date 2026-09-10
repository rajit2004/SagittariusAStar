
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Mapping, Optional
from urllib.parse import urlsplit, urlunsplit

from fastapi import Request

from utils.logger import logger

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

TWILIO_SIGNATURE_HEADER = "X-Twilio-Signature"

CHANNEL_TELEGRAM = "telegram"
CHANNEL_WHATSAPP = "whatsapp"

_warned: set = set()

class WebhookVerificationError(Exception):

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason

def telegram_secret() -> Optional[str]:
    value = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    return value or None

def twilio_auth_token() -> Optional[str]:
    value = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    return value or None

def verification_configured(channel: str) -> bool:
    if channel == CHANNEL_TELEGRAM:
        return telegram_secret() is not None
    if channel == CHANNEL_WHATSAPP:
        return twilio_auth_token() is not None
    return False

def _warn_unverified(channel: str) -> None:
    if channel in _warned:
        return
    _warned.add(channel)
    logger.bind(channel=channel).warning(
        "Webhook signature verification is disabled — no secret is "
        "configured for this channel. Anyone who can reach this URL can "
        "post to it."
    )

def reset_warning_state() -> None:
    _warned.clear()

def verify_telegram(request: Request) -> None:
    expected = telegram_secret()
    if expected is None:
        _warn_unverified(CHANNEL_TELEGRAM)
        return

    provided = request.headers.get(TELEGRAM_SECRET_HEADER)
    if not provided:
        raise WebhookVerificationError("missing secret token header")

    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("secret token mismatch")

def _public_url(request: Request) -> str:
    received = str(request.url)
    base = (os.getenv("WEBHOOK_PUBLIC_BASE_URL") or "").strip()
    if not base:
        return received

    parsed_base = urlsplit(base)
    parsed_received = urlsplit(received)
    return urlunsplit(
        (
            parsed_base.scheme or parsed_received.scheme,
            parsed_base.netloc or parsed_received.netloc,
            parsed_received.path,
            parsed_received.query,
            "",
        )
    )

def twilio_signature(auth_token: str, url: str, params: Mapping[str, str]) -> str:
    payload = url
    for name in sorted(params):
        payload += name + (params[name] or "")

    digest = hmac.new(
        auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode("utf-8")

def verify_twilio(request: Request, params: Mapping[str, str]) -> None:
    auth_token = twilio_auth_token()
    if auth_token is None:
        _warn_unverified(CHANNEL_WHATSAPP)
        return

    provided = request.headers.get(TWILIO_SIGNATURE_HEADER)
    if not provided:
        raise WebhookVerificationError("missing signature header")

    expected = twilio_signature(auth_token, _public_url(request), params)
    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("signature mismatch")

__all__ = [
    "CHANNEL_TELEGRAM",
    "CHANNEL_WHATSAPP",
    "TELEGRAM_SECRET_HEADER",
    "TWILIO_SIGNATURE_HEADER",
    "WebhookVerificationError",
    "reset_warning_state",
    "telegram_secret",
    "twilio_auth_token",
    "twilio_signature",
    "verification_configured",
    "verify_telegram",
    "verify_twilio",
]
