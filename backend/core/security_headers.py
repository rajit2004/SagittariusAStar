
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Tuple

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_HSTS = "max-age=63072000; includeSubDomains; preload"

DEFAULT_CONTENT_TYPE_OPTIONS = "nosniff"

DEFAULT_FRAME_OPTIONS = "DENY"

DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"

DEFAULT_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=(), "
    "xr-spatial-tracking=()"
)

DEFAULT_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "upgrade-insecure-requests"
)

DEFAULT_COOP = "same-origin-allow-popups"
DEFAULT_CORP = "same-origin"

DEFAULT_STRIP_SERVER_HEADER = True

_DISABLED_VALUES = frozenset({"", "off", "none", "disabled", "false", "0"})

HSTS_HEADER = "strict-transport-security"
CONTENT_TYPE_OPTIONS_HEADER = "x-content-type-options"
FRAME_OPTIONS_HEADER = "x-frame-options"
REFERRER_POLICY_HEADER = "referrer-policy"
PERMISSIONS_POLICY_HEADER = "permissions-policy"
CSP_HEADER = "content-security-policy"
COOP_HEADER = "cross-origin-opener-policy"
CORP_HEADER = "cross-origin-resource-policy"

_SECURE_SCHEMES = frozenset({"https", "wss"})

_FORWARDED_PROTO_HEADERS: Tuple[str, ...] = (
    "x-forwarded-proto",
    "x-forwarded-protocol",
    "x-forwarded-scheme",
)

def _env(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip()

def _is_disabled(value: str) -> bool:
    return value.strip().lower() in _DISABLED_VALUES

def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _DISABLED_VALUES

def build_header_policy() -> Dict[str, str]:
    candidates = (
        (CONTENT_TYPE_OPTIONS_HEADER, _env("SECURITY_CONTENT_TYPE_OPTIONS", DEFAULT_CONTENT_TYPE_OPTIONS)),
        (FRAME_OPTIONS_HEADER, _env("SECURITY_FRAME_OPTIONS", DEFAULT_FRAME_OPTIONS)),
        (REFERRER_POLICY_HEADER, _env("SECURITY_REFERRER_POLICY", DEFAULT_REFERRER_POLICY)),
        (PERMISSIONS_POLICY_HEADER, _env("SECURITY_PERMISSIONS_POLICY", DEFAULT_PERMISSIONS_POLICY)),
        (CSP_HEADER, _env("SECURITY_CSP", DEFAULT_CSP)),
        (COOP_HEADER, _env("SECURITY_COOP", DEFAULT_COOP)),
        (CORP_HEADER, _env("SECURITY_CORP", DEFAULT_CORP)),
    )
    return {name: value for name, value in candidates if not _is_disabled(value)}

def resolve_scheme(scope: Scope, headers: Headers) -> str:
    for header in _FORWARDED_PROTO_HEADERS:
        forwarded = headers.get(header)
        if forwarded:
            first = forwarded.split(",")[0].strip().lower()
            if first:
                return first
    return str(scope.get("scheme", "http")).lower()

def _wants_hsts(scheme: str) -> bool:
    return scheme in _SECURE_SCHEMES

class SecurityHeadersMiddleware:

    def __init__(
        self,
        app: ASGIApp,
        headers: Optional[Dict[str, str]] = None,
        hsts: Optional[str] = None,
        strip_server_header: Optional[bool] = None,
        exclude_paths: Optional[Iterable[str]] = None,
    ) -> None:
        self.app = app

        self.headers = build_header_policy() if headers is None else dict(headers)
        resolved_hsts = _env("SECURITY_HSTS", DEFAULT_HSTS) if hsts is None else hsts
        self.hsts = None if _is_disabled(resolved_hsts) else resolved_hsts
        self.strip_server_header = (
            _env_flag("SECURITY_STRIP_SERVER_HEADER", DEFAULT_STRIP_SERVER_HEADER)
            if strip_server_header is None
            else strip_server_header
        )
        self.exclude_paths = set(exclude_paths or ())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":

            await self.app(scope, receive, send)
            return

        if scope.get("path") in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        scheme = resolve_scheme(scope, Headers(scope=scope))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.apply(MutableHeaders(scope=message), scheme=scheme)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def apply(self, headers: MutableHeaders, *, scheme: str) -> None:
        for name, value in self.headers.items():
            if name not in headers:
                headers[name] = value

        if self.hsts and _wants_hsts(scheme) and HSTS_HEADER not in headers:
            headers[HSTS_HEADER] = self.hsts

        if self.strip_server_header and "server" in headers:
            del headers["server"]

def applied_header_names(*, secure: bool = True) -> List[str]:
    names = list(build_header_policy().keys())
    if secure and not _is_disabled(_env("SECURITY_HSTS", DEFAULT_HSTS)):
        names.append(HSTS_HEADER)
    return names

_fallback_middleware: Optional[SecurityHeadersMiddleware] = None

def _fallback() -> SecurityHeadersMiddleware:
    global _fallback_middleware
    if _fallback_middleware is None:
        _fallback_middleware = SecurityHeadersMiddleware(app=None)
    return _fallback_middleware

def reset_fallback_cache() -> None:
    global _fallback_middleware
    _fallback_middleware = None

def secure_response(response, request=None):
    scheme = "http"
    if request is not None:
        try:
            scheme = resolve_scheme(request.scope, request.headers)
        except Exception:

            scheme = "http"
    _fallback().apply(MutableHeaders(raw=response.raw_headers), scheme=scheme)
    return response

__all__ = [
    "CONTENT_TYPE_OPTIONS_HEADER",
    "COOP_HEADER",
    "CORP_HEADER",
    "CSP_HEADER",
    "DEFAULT_CONTENT_TYPE_OPTIONS",
    "DEFAULT_COOP",
    "DEFAULT_CORP",
    "DEFAULT_CSP",
    "DEFAULT_FRAME_OPTIONS",
    "DEFAULT_HSTS",
    "DEFAULT_PERMISSIONS_POLICY",
    "DEFAULT_REFERRER_POLICY",
    "DEFAULT_STRIP_SERVER_HEADER",
    "FRAME_OPTIONS_HEADER",
    "HSTS_HEADER",
    "PERMISSIONS_POLICY_HEADER",
    "REFERRER_POLICY_HEADER",
    "SecurityHeadersMiddleware",
    "applied_header_names",
    "build_header_policy",
    "reset_fallback_cache",
    "resolve_scheme",
    "secure_response",
]
