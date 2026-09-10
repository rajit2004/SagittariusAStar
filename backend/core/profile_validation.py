
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

MAX_LAST_PERIOD_AGE_DAYS = 3653

FUTURE_GRACE_DAYS = 1

MAX_DATE_CHARS = 64

def normalize_last_period(value: Any) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
    elif isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) > MAX_DATE_CHARS:
            raise ValueError(
                "last_period must be a date in YYYY-MM-DD form"
            )
        parsed = _parse_date(text)
    else:
        raise ValueError("last_period must be a date in YYYY-MM-DD form")

    _check_range(parsed)
    return parsed.isoformat()

def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(candidate).date()
    except ValueError:
        raise ValueError(
            f"last_period must be a date in YYYY-MM-DD form (got {text!r})"
        ) from None

def _check_range(parsed: date) -> None:
    today = datetime.now(timezone.utc).date()

    latest = today + timedelta(days=FUTURE_GRACE_DAYS)
    if parsed > latest:
        raise ValueError(
            "last_period cannot be in the future "
            f"(got {parsed.isoformat()}, today is {today.isoformat()})"
        )

    earliest = today - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS)
    if parsed < earliest:
        raise ValueError(
            "last_period is too far in the past "
            f"(got {parsed.isoformat()}, the earliest accepted is "
            f"{earliest.isoformat()})"
        )

__all__ = [
    "FUTURE_GRACE_DAYS",
    "MAX_DATE_CHARS",
    "MAX_LAST_PERIOD_AGE_DAYS",
    "normalize_last_period",
]
