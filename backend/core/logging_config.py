
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Iterable, Mapping, Optional, Set

from loguru import logger

from core.request_context import get_request_id

REDACTED = "[redacted]"

SENSITIVE_KEY_FRAGMENTS: frozenset = frozenset(
    {

        "phone",
        "email",
        "full_name",
        "username",
        "address",
        "city",
        "state",

        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "credential",
        "cookie",
        "session",
        "id_token",
        "otp",

        "symptom",
        "symptoms",
        "notes",
        "note",
        "mood",
        "flow_intensity",
        "stress_level",
        "sleep_hours",
        "last_period",
        "weight_kg",
        "height_cm",
        "message",
        "messages",
    }
)

_MAX_REDACT_DEPTH = 6

_MAX_SEQUENCE_ITEMS = 20

def is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)

def redact(value: Any, _depth: int = 0) -> Any:
    if _depth >= _MAX_REDACT_DEPTH:
        return "[truncated]"

    if isinstance(value, Mapping):
        redacted: Dict[Any, Any] = {}
        for key, inner in value.items():
            if is_sensitive_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact(inner, _depth + 1)
        return redacted

    if isinstance(value, (list, tuple, set, frozenset)):
        items: Iterable[Any] = list(value)[:_MAX_SEQUENCE_ITEMS]
        rendered = [redact(item, _depth + 1) for item in items]
        if len(value) > _MAX_SEQUENCE_ITEMS:
            rendered.append(f"[+{len(value) - _MAX_SEQUENCE_ITEMS} more]")
        return rendered

    return value

def redact_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    return {
        name: (REDACTED if is_sensitive_key(name) else value)
        for name, value in headers.items()
    }

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<level>{level: <8}</level> "
    "<cyan>{extra[request_id]}</cyan> "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
    "<level>{message}</level>"
)

_JSON_BASE_FIELDS = ("timestamp", "level", "logger", "message", "request_id")

_configured = False

def _patch_record(record: Dict[str, Any]) -> None:
    extra = record["extra"]

    extra.setdefault("request_id", "-")

    request_id = get_request_id()
    if request_id:
        extra["request_id"] = request_id

    if _redaction_enabled():
        for key in list(extra.keys()):
            if key == "request_id":
                continue
            if is_sensitive_key(key):
                extra[key] = REDACTED
            else:
                extra[key] = redact(extra[key])

_redact_enabled = True

def _redaction_enabled() -> bool:
    return _redact_enabled

def _resolve_redaction_setting() -> bool:
    return os.getenv("LOG_REDACT", "true").strip().lower() not in {"false", "0", "no"}

def _json_sink(message: Any) -> None:
    record = message.record
    payload: Dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": f"{record['name']}:{record['function']}:{record['line']}",
        "message": record["message"],
        "request_id": record["extra"].get("request_id", "-"),
    }

    context = {k: v for k, v in record["extra"].items() if k != "request_id"}
    if context:
        payload["context"] = context

    if record["exception"] is not None:
        exc = record["exception"]
        payload["exception"] = {
            "type": getattr(exc.type, "__name__", str(exc.type)),
            "value": str(exc.value),
        }

    sys.stdout.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")

class InterceptHandler(logging.Handler):

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def _intercepted_logger_names() -> Set[str]:
    return {
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "httpx",
        "httpcore",
        "google",
        "firebase_admin",
    }

def configure_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    force: bool = False,
) -> None:
    global _configured, _redact_enabled
    if _configured and not force:
        return

    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    resolved_format = (log_format or os.getenv("LOG_FORMAT") or "console").lower()
    _redact_enabled = _resolve_redaction_setting()

    logger.remove()
    logger.configure(patcher=_patch_record)

    if resolved_format == "json":
        logger.add(
            _json_sink,
            level=resolved_level,
            backtrace=False,

            diagnose=False,
            enqueue=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=resolved_level,
            format=_CONSOLE_FORMAT,
            colorize=True,
            backtrace=True,
            diagnose=False,
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in _intercepted_logger_names():
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    _configured = True

__all__ = [
    "REDACTED",
    "SENSITIVE_KEY_FRAGMENTS",
    "InterceptHandler",
    "configure_logging",
    "is_sensitive_key",
    "redact",
    "redact_headers",
]
