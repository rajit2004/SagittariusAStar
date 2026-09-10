
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from utils.logger import logger

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"

_SEVERITY = {STATUS_OK: 0, STATUS_DEGRADED: 1, STATUS_DOWN: 2}

DEFAULT_CHECK_TIMEOUT_SECONDS = float(os.getenv("HEALTH_CHECK_TIMEOUT", "3.0"))

HEALTH_PROBE_COLLECTION = "health_probe"
HEALTH_PROBE_DOCUMENT = "readiness"

@dataclass
class ComponentHealth:

    name: str
    status: str
    required: bool
    detail: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "required": self.required,
            "detail": self.detail,
            "durationMs": round(self.duration_ms, 2),
        }

@dataclass
class HealthReport:
    status: str
    components: List[ComponentHealth] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not any(
            component.required and component.status == STATUS_DOWN
            for component in self.components
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "components": [component.to_dict() for component in self.components],
        }

def build_info() -> Dict[str, Optional[str]]:
    commit = os.getenv("GIT_COMMIT") or os.getenv("VERCEL_GIT_COMMIT_SHA")
    return {
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "commit": (commit[:12] if commit else "unknown"),
        "builtAt": os.getenv("BUILD_TIME", "unknown"),
        "environment": os.getenv("APP_ENV", "development"),
    }

def _configured(var: str) -> bool:
    value = os.getenv(var)
    return bool(value and value.strip())

def check_firestore() -> ComponentHealth:
    from services import firestore_service as fs

    client = fs.db

    if client is None:
        return ComponentHealth(
            name="firestore",
            status=STATUS_DOWN,
            required=True,
            detail="No Firestore client was initialised.",
        )

    if isinstance(client, fs.MockFirestoreClient):
        return ComponentHealth(
            name="firestore",
            status=STATUS_DOWN,
            required=True,
            detail=(
                "Running on the in-memory mock database. Firebase credentials "
                "are missing or unreadable; all data is lost on restart."
            ),
        )

    client.collection(HEALTH_PROBE_COLLECTION).document(HEALTH_PROBE_DOCUMENT).get()

    return ComponentHealth(
        name="firestore",
        status=STATUS_OK,
        required=True,
        detail="Connected.",
    )

def check_auth_config() -> ComponentHealth:
    if not _configured("JWT_SECRET"):
        return ComponentHealth(
            name="auth",
            status=STATUS_DOWN,
            required=True,
            detail="JWT_SECRET is not configured; tokens cannot be issued.",
        )
    return ComponentHealth(
        name="auth",
        status=STATUS_OK,
        required=True,
        detail="Signing key configured.",
    )

def check_assistant_config() -> ComponentHealth:
    if not _configured("GEMINI_API_KEY"):
        return ComponentHealth(
            name="assistant",
            status=STATUS_DEGRADED,
            required=False,
            detail="GEMINI_API_KEY is not configured; /assistant/chat will fail.",
        )
    return ComponentHealth(
        name="assistant",
        status=STATUS_OK,
        required=False,
        detail="API key configured.",
    )

def check_sms_config() -> ComponentHealth:
    required_vars = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER")
    missing = [name for name in required_vars if not _configured(name)]

    if len(missing) == len(required_vars):
        return ComponentHealth(
            name="sms",
            status=STATUS_DEGRADED,
            required=False,
            detail="Twilio is not configured; SMS summaries are unavailable.",
        )
    if missing:
        return ComponentHealth(
            name="sms",
            status=STATUS_DEGRADED,
            required=False,
            detail=(
                "Twilio is partially configured; missing: "
                f"{', '.join(missing)}. SMS summaries will fail at send time."
            ),
        )
    return ComponentHealth(
        name="sms",
        status=STATUS_OK,
        required=False,
        detail="Credentials configured.",
    )

CHECKS: List[Callable[[], ComponentHealth]] = [
    check_firestore,
    check_auth_config,
    check_assistant_config,
    check_sms_config,
]

def _run_one(
    check: Callable[[], ComponentHealth], timeout: float
) -> ComponentHealth:
    started = time.perf_counter()
    name = getattr(check, "__name__", "check").replace("check_", "")
    pool = ThreadPoolExecutor(max_workers=1)

    try:
        result = pool.submit(check).result(timeout=timeout)
        result.duration_ms = (time.perf_counter() - started) * 1000
        pool.shutdown(wait=False)
        return result
    except FutureTimeout:
        pool.shutdown(wait=False, cancel_futures=True)
        logger.warning(f"Health check {name!r} timed out after {timeout}s")
        return ComponentHealth(
            name=name,
            status=STATUS_DOWN,
            required=True,
            detail=f"Check did not respond within {timeout} seconds.",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:
        pool.shutdown(wait=False)

        logger.exception(f"Health check {name!r} raised: {exc}")
        return ComponentHealth(
            name=name,
            status=STATUS_DOWN,
            required=True,
            detail="Check failed. See server logs for details.",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

def run_checks(timeout: Optional[float] = None) -> HealthReport:
    limit = timeout if timeout is not None else DEFAULT_CHECK_TIMEOUT_SECONDS
    components = [_run_one(check, limit) for check in CHECKS]

    overall = STATUS_OK
    for component in components:
        if _SEVERITY[component.status] > _SEVERITY[overall]:
            overall = component.status

    return HealthReport(status=overall, components=components)

def liveness() -> Dict[str, Any]:
    return {
        "status": STATUS_OK,
        "service": "Rhythma API",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }
