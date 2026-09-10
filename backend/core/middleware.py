
from __future__ import annotations

import time
from typing import Iterable, Optional, Set

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.request_context import (
    REQUEST_ID_HEADER,
    normalize_request_id,
    set_request_context,
)
from utils.logger import logger

DEFAULT_QUIET_PATHS: Set[str] = {
    "/",
    "/api/v1/health",
    "/api/v1/health/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}

SLOW_REQUEST_MS = 1500.0

class RequestContextMiddleware:

    def __init__(
        self,
        app: ASGIApp,
        quiet_paths: Optional[Iterable[str]] = None,
        slow_request_ms: float = SLOW_REQUEST_MS,
    ) -> None:
        self.app = app
        self.quiet_paths = set(quiet_paths) if quiet_paths is not None else set(DEFAULT_QUIET_PATHS)
        self.slow_request_ms = slow_request_ms

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":

            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = normalize_request_id(headers.get(REQUEST_ID_HEADER))
        method = scope.get("method", "-")
        path = scope.get("path", "-")

        tokens = set_request_context(request_id, method=method, path=path)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:

            self._log_access(
                method=method,
                path=path,
                status_code=500,
                duration_ms=self._elapsed_ms(started),
                query=scope.get("query_string", b""),
                client=scope.get("client"),
                failed=True,
            )
            raise
        else:
            self._log_access(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=self._elapsed_ms(started),
                query=scope.get("query_string", b""),
                client=scope.get("client"),
                failed=False,
            )
        finally:
            tokens.reset()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def _log_access(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        query: bytes,
        client,
        failed: bool,
    ) -> None:
        bound = logger.bind(
            http_method=method,
            http_path=path,
            http_status=status_code,
            duration_ms=duration_ms,

            has_query=bool(query),
            client_ip=client[0] if client else None,
        )

        message = "{} {} → {} ({}ms)".format(method, path, status_code, duration_ms)

        if failed or status_code >= 500:
            bound.error(message)
        elif status_code >= 400:
            bound.warning(message)
        elif duration_ms >= self.slow_request_ms:
            bound.warning("Slow request: " + message)
        elif path in self.quiet_paths:
            bound.debug(message)
        else:
            bound.info(message)

__all__ = ["DEFAULT_QUIET_PATHS", "SLOW_REQUEST_MS", "RequestContextMiddleware"]
