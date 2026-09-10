
from __future__ import annotations

import os
import re
import string
from dataclasses import dataclass
from typing import List, Optional

from core.errors import AppError

DEFAULT_MIN_LENGTH = 8

MAX_PASSWORD_BYTES = 72

MIN_IDENTIFIER_FRAGMENT = 4

COMMON_PASSWORDS = frozenset(
    {
        "123456", "123456789", "12345678", "1234567", "1234567890", "12345",
        "password", "password1", "password123", "passw0rd", "p@ssw0rd",
        "qwerty", "qwerty123", "qwertyuiop", "asdfghjkl", "zxcvbnm",
        "111111", "000000", "123123", "654321", "666666", "888888",
        "abc123", "abcd1234", "a1b2c3d4", "letmein", "welcome", "welcome1",
        "iloveyou", "monkey", "dragon", "sunshine", "princess", "football",
        "baseball", "superman", "trustno1", "master", "shadow", "michael",
        "jennifer", "computer", "internet", "samsung", "google", "facebook",
        "whatsapp", "india123", "indian123", "bharat123", "krishna",
        "ganesh", "chennai", "mumbai123", "delhi123", "admin", "admin123",
        "root", "test123", "changeme", "secret", "login", "pass1234",
        "rhythma", "rhythma123", "period123", "health123",
    }
)

_SEQUENCES = (
    string.ascii_lowercase,
    string.digits,
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)

_MAX_SEQUENCE_RUN = 5

def min_length() -> int:
    raw = os.getenv("PASSWORD_MIN_LENGTH")
    if raw is None:
        return DEFAULT_MIN_LENGTH
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MIN_LENGTH
    return max(value, DEFAULT_MIN_LENGTH)

@dataclass(frozen=True)
class PasswordFailure:

    code: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}

class WeakPasswordError(AppError):

    status_code = 422
    code = "weak_password"
    message = "That password doesn't meet the requirements."

def _identifier_fragments(email: Optional[str], username: Optional[str]) -> List[str]:
    fragments: List[str] = []

    if username:
        fragments.append(username)

    if email and "@" in email:
        local, _, domain = email.partition("@")
        fragments.append(local)
        fragments.extend(re.split(r"[._\-+]", local))

        domain_parts = domain.split(".")
        if domain_parts:
            fragments.append(domain_parts[0])
    elif email:
        fragments.append(email)

    return [f.lower() for f in fragments if len(f) >= MIN_IDENTIFIER_FRAGMENT]

def _has_long_sequence(password: str) -> bool:
    lowered = password.lower()
    for source in _SEQUENCES:
        reverse = source[::-1]
        for start in range(len(source) - _MAX_SEQUENCE_RUN + 1):
            if source[start : start + _MAX_SEQUENCE_RUN] in lowered:
                return True
            if reverse[start : start + _MAX_SEQUENCE_RUN] in lowered:
                return True
    return False

def validate_password(
    password: str,
    *,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> List[PasswordFailure]:
    failures: List[PasswordFailure] = []
    required = min_length()

    if password is None or password == "":

        return [
            PasswordFailure(
                code="password_required",
                message="Please enter a password.",
            )
        ]

    if password.strip() == "":
        return [
            PasswordFailure(
                code="password_blank",
                message="A password cannot be only spaces.",
            )
        ]

    if len(password) < required:
        failures.append(
            PasswordFailure(
                code="too_short",
                message=f"Use at least {required} characters.",
            )
        )

    byte_length = len(password.encode("utf-8"))
    if byte_length > MAX_PASSWORD_BYTES:
        failures.append(
            PasswordFailure(
                code="too_long",
                message=(
                    f"That password is too long to be stored safely "
                    f"({byte_length} bytes; the limit is {MAX_PASSWORD_BYTES}). "
                    "Please shorten it."
                ),
            )
        )

    if password.lower() in COMMON_PASSWORDS:
        failures.append(
            PasswordFailure(
                code="too_common",
                message="That password is one of the most commonly used ones. Please pick another.",
            )
        )

    lowered = password.lower()
    for fragment in _identifier_fragments(email, username):
        if fragment in lowered:
            failures.append(
                PasswordFailure(
                    code="contains_identifier",
                    message="Your password shouldn't contain your email address or username.",
                )
            )
            break

    if len(set(password)) < 4 and len(password) >= 4:
        failures.append(
            PasswordFailure(
                code="not_varied_enough",
                message="Use a few more different characters — this one repeats too much.",
            )
        )

    if _has_long_sequence(password):
        failures.append(
            PasswordFailure(
                code="sequential",
                message="Avoid runs like 12345 or qwerty — they're the first thing guessed.",
            )
        )

    return failures

def enforce_password_policy(
    password: str,
    *,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> None:
    failures = validate_password(password, email=email, username=username)
    if not failures:
        return

    raise WeakPasswordError(
        details=[failure.to_dict() for failure in failures],
    )

def requirements() -> dict:
    return {
        "minLength": min_length(),
        "maxBytes": MAX_PASSWORD_BYTES,
        "rules": [
            {
                "code": "too_short",
                "message": f"At least {min_length()} characters.",
            },
            {
                "code": "too_long",
                "message": (
                    f"No longer than {MAX_PASSWORD_BYTES} bytes — note that "
                    "letters in Indian-language scripts take about three "
                    "bytes each."
                ),
            },
            {
                "code": "too_common",
                "message": "Not one of the most commonly used passwords.",
            },
            {
                "code": "contains_identifier",
                "message": "Doesn't contain your email address or username.",
            },
            {
                "code": "not_varied_enough",
                "message": "More than a few repeated characters.",
            },
            {
                "code": "sequential",
                "message": "No long runs like 12345 or qwerty.",
            },
        ],
    }
