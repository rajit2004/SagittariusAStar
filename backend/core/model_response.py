
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

FINISH_REASON_UNSPECIFIED = 0
FINISH_STOP = 1
FINISH_MAX_TOKENS = 2
FINISH_SAFETY = 3
FINISH_RECITATION = 4
FINISH_OTHER = 5

FINISH_REASON_NAMES = {
    FINISH_REASON_UNSPECIFIED: "FINISH_REASON_UNSPECIFIED",
    FINISH_STOP: "STOP",
    FINISH_MAX_TOKENS: "MAX_TOKENS",
    FINISH_SAFETY: "SAFETY",
    FINISH_RECITATION: "RECITATION",
    FINISH_OTHER: "OTHER",
}

FINISH_REASON_VALUES = {name: value for value, name in FINISH_REASON_NAMES.items()}

STATUS_OK = "ok"

STATUS_TRUNCATED = "truncated"

STATUS_BLOCKED_SAFETY = "blocked_safety"

STATUS_BLOCKED_RECITATION = "blocked_recitation"

STATUS_UNAVAILABLE = "unavailable"

ANSWER_STATUSES = frozenset({STATUS_OK, STATUS_TRUNCATED})

MESSAGE_SAFETY = (
    "I'm not able to answer that one. It's not a judgement on your question — "
    "there are topics I'm set up to leave to a doctor. Please speak to a "
    "healthcare professional about this."
)

MESSAGE_RECITATION = (
    "I couldn't answer that one in my own words. Please try asking it a "
    "different way, or speak to a healthcare professional."
)

MESSAGE_UNAVAILABLE = (
    "I'm sorry, I couldn't produce an answer just now. Please try asking "
    "again, or speak to a healthcare professional."
)

MESSAGE_EMPTY = "I'm sorry, I couldn't produce an answer just now. Please try again."

TRUNCATION_NOTE = "… (this answer was shortened — ask me to continue if you'd like the rest.)"

@dataclass(frozen=True)
class ModelOutcome:

    status: str
    text: str

    finish_reason: Optional[str] = None

    from_model: bool = False

    @property
    def was_shortened(self) -> bool:
        return self.status == STATUS_TRUNCATED

    @property
    def is_answer(self) -> bool:
        return self.status in ANSWER_STATUSES

def finish_reason_value(raw: Any) -> Optional[int]:
    if raw is None:
        return None

    if isinstance(raw, bool):

        return None
    if isinstance(raw, int):
        return int(raw)

    text = str(raw).strip()
    if not text:
        return None

    if text.isdigit():
        return int(text)

    name = text.rsplit(".", 1)[-1].upper()
    return FINISH_REASON_VALUES.get(name)

def finish_reason_name(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return FINISH_REASON_NAMES.get(value, f"UNKNOWN_{value}")

def candidate_text(candidate: Any) -> str:
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []

    chunks = []
    for part in parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            chunks.append(text)

    return "".join(chunks).strip()

def response_text(response: Any) -> str:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        text = candidate_text(candidate)
        if text:
            return text

    try:
        text = getattr(response, "text", None)
    except Exception:

        return ""

    return text.strip() if isinstance(text, str) else ""

def interpret(response: Any) -> ModelOutcome:
    candidates = getattr(response, "candidates", None) or []

    if not candidates:

        blocked = _prompt_block_reason(response)
        if blocked:
            return ModelOutcome(
                status=STATUS_BLOCKED_SAFETY,
                text=MESSAGE_SAFETY,
                finish_reason=blocked,
            )

        text = response_text(response)
        if text:
            return ModelOutcome(
                status=STATUS_OK, text=text, finish_reason=None, from_model=True
            )

        return ModelOutcome(
            status=STATUS_UNAVAILABLE,
            text=MESSAGE_UNAVAILABLE,
            finish_reason=None,
        )

    candidate = candidates[0]
    value = finish_reason_value(getattr(candidate, "finish_reason", None))
    name = finish_reason_name(value)
    text = candidate_text(candidate) or response_text(response)

    if value == FINISH_SAFETY:
        return ModelOutcome(
            status=STATUS_BLOCKED_SAFETY, text=MESSAGE_SAFETY, finish_reason=name
        )

    if value == FINISH_RECITATION:
        return ModelOutcome(
            status=STATUS_BLOCKED_RECITATION,
            text=MESSAGE_RECITATION,
            finish_reason=name,
        )

    if value == FINISH_MAX_TOKENS:

        if text:
            return ModelOutcome(
                status=STATUS_TRUNCATED,
                text=f"{text} {TRUNCATION_NOTE}",
                finish_reason=name,
                from_model=True,
            )
        return ModelOutcome(
            status=STATUS_UNAVAILABLE, text=MESSAGE_UNAVAILABLE, finish_reason=name
        )

    if text:
        return ModelOutcome(
            status=STATUS_OK, text=text, finish_reason=name, from_model=True
        )

    return ModelOutcome(
        status=STATUS_UNAVAILABLE, text=MESSAGE_EMPTY, finish_reason=name
    )

def _prompt_block_reason(response: Any) -> Optional[str]:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is None:
        return None

    raw = getattr(feedback, "block_reason", None)
    if raw is None:
        return None

    text = str(raw).strip()
    if not text or text.upper().endswith("UNSPECIFIED"):
        return None

    return text.rsplit(".", 1)[-1].upper()
