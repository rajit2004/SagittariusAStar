
from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[Optional[str]] = ContextVar("rhythma_request_id", default=None)
_request_method: ContextVar[Optional[str]] = ContextVar("rhythma_request_method", default=None)
_request_path: ContextVar[Optional[str]] = ContextVar("rhythma_request_path", default=None)

def new_request_id() -> str:
    return uuid.uuid4().hex

def normalize_request_id(candidate: Optional[str]) -> str:
    if candidate and _REQUEST_ID_PATTERN.match(candidate):
        return candidate
    return new_request_id()

def set_request_context(
    request_id: str,
    method: Optional[str] = None,
    path: Optional[str] = None,
) -> "RequestContextTokens":
    return RequestContextTokens(
        request_id=_request_id.set(request_id),
        method=_request_method.set(method),
        path=_request_path.set(path),
    )

class RequestContextTokens:

    __slots__ = ("request_id", "method", "path")

    def __init__(
        self,
        request_id: Token,
        method: Token,
        path: Token,
    ) -> None:
        self.request_id = request_id
        self.method = method
        self.path = path

    def reset(self) -> None:
        for var, token in (
            (_request_id, self.request_id),
            (_request_method, self.method),
            (_request_path, self.path),
        ):
            try:
                var.reset(token)
            except ValueError:

                var.set(None)

def get_request_id() -> Optional[str]:
    return _request_id.get()

def get_request_method() -> Optional[str]:
    return _request_method.get()

def get_request_path() -> Optional[str]:
    return _request_path.get()

def clear_request_context() -> None:
    _request_id.set(None)
    _request_method.set(None)
    _request_path.set(None)
