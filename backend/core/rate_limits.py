
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status

from core.client_address import client_address
from services.rate_limit_service import RateLimitService

@dataclass(frozen=True)
class RateLimitPolicy:

    name: str
    default_limit: int
    default_window: int

    message: str

    @property
    def env_prefix(self) -> str:
        return f"RATE_LIMIT_{self.name.upper()}"

    def _env_int(self, suffix: str, fallback: int) -> int:
        raw = os.getenv(f"{self.env_prefix}_{suffix}")
        if raw is None:
            return fallback
        try:
            value = int(raw)
        except ValueError:
            return fallback

        return value if value > 0 else fallback

    @property
    def limit(self) -> int:
        return self._env_int("MAX", self.default_limit)

    @property
    def window_seconds(self) -> int:
        return self._env_int("WINDOW", self.default_window)

    def key_for(self, identifier: str) -> str:
        digest = hashlib.sha256(identifier.strip().lower().encode("utf-8"))
        return f"{self.name}:{digest.hexdigest()[:32]}"

LOGIN_IP = RateLimitPolicy(
    name="login_ip",
    default_limit=10,
    default_window=900,
    message="Too many login attempts from this device. Please try again in {seconds} seconds.",
)

LOGIN_ACCOUNT = RateLimitPolicy(
    name="login_account",
    default_limit=5,
    default_window=900,
    message="Too many failed login attempts for this account. Please try again in {seconds} seconds.",
)

FIREBASE_LOGIN_IP = RateLimitPolicy(
    name="firebase_login_ip",

    default_limit=10,
    default_window=300,
    message="Too many login attempts. Please wait {seconds} seconds.",
)

REGISTER_IP = RateLimitPolicy(
    name="register_ip",
    default_limit=5,
    default_window=3600,
    message="Too many accounts created from this device. Please try again in {seconds} seconds.",
)

PROVIDER_REGISTER_IP = RateLimitPolicy(
    name="provider_register_ip",
    default_limit=3,
    default_window=3600,
    message=(
        "Too many provider accounts created from this device. "
        "Please try again in {seconds} seconds."
    ),
)

PASSWORD_RESET_REQUEST_ACCOUNT = RateLimitPolicy(
    name="password_reset_request_account",
    default_limit=3,
    default_window=3600,
    message="A reset link was already requested for this account. Please try again in {seconds} seconds.",
)

PASSWORD_RESET_REQUEST_IP = RateLimitPolicy(
    name="password_reset_request_ip",
    default_limit=10,
    default_window=3600,
    message="Too many password reset requests. Please try again in {seconds} seconds.",
)

PASSWORD_RESET_CONFIRM_IP = RateLimitPolicy(
    name="password_reset_confirm_ip",
    default_limit=5,
    default_window=3600,
    message="Too many password reset attempts. Please try again in {seconds} seconds.",
)

EMAIL_VERIFY_IP = RateLimitPolicy(
    name="email_verify_ip",
    default_limit=10,
    default_window=3600,
    message="Too many verification attempts. Please try again in {seconds} seconds.",
)

VERIFICATION_RESEND_ACCOUNT = RateLimitPolicy(
    name="verification_resend_account",
    default_limit=3,
    default_window=3600,
    message="A verification email was already sent. Please try again in {seconds} seconds.",
)

BOT_WEBHOOK_IP = RateLimitPolicy(
    name="bot_webhook_ip",
    default_limit=60,
    default_window=60,
    message="Too many webhook deliveries. Please retry in {seconds} seconds.",
)

BOT_LINK_CODE_ACCOUNT = RateLimitPolicy(
    name="bot_link_code_account",
    default_limit=5,
    default_window=3600,
    message=(
        "Too many connection codes requested. Please try again in "
        "{seconds} seconds."
    ),
)

TOKEN_REFRESH_IP = RateLimitPolicy(
    name="token_refresh_ip",
    default_limit=30,
    default_window=300,
    message="Too many token refresh attempts. Please try again in {seconds} seconds.",
)

def client_ip(request: Optional[Request]) -> str:
    return client_address(request)

def enforce(policy: RateLimitPolicy, identifier: str) -> None:
    remaining = RateLimitService.is_rate_limited(
        key=policy.key_for(identifier),
        limit=policy.limit,
        window_seconds=policy.window_seconds,
    )
    if remaining is None:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=policy.message.format(seconds=remaining),
        headers={"Retry-After": str(remaining)},
    )

def clear(policy: RateLimitPolicy, identifier: str) -> None:
    RateLimitService.reset(policy.key_for(identifier))
