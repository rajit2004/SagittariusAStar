
from __future__ import annotations

from typing import Optional

__all__ = ["normalize_email", "same_email"]

def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()

def same_email(left: Optional[str], right: Optional[str]) -> bool:
    normalized = normalize_email(left)
    return bool(normalized) and normalized == normalize_email(right)
