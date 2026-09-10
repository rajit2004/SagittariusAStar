
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.logging_config import redact
from core.request_context import REQUEST_ID_HEADER, get_request_id
from core.security_headers import secure_response
from utils.logger import logger

class AppError(Exception):

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Something went wrong. Please try again."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        details: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        self.headers = headers or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "The request could not be processed."

class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Could not validate credentials"

class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Not authorized"

class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."

class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "That resource already exists."

class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."

class UpstreamServiceError(AppError):

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "upstream_unavailable"
    message = "A required service is temporarily unavailable. Please try again."

class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "Something went wrong. Please try again."

_STATUS_CODE_NAMES: Dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",

    413: "payload_too_large",
    422: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_501_NOT_IMPLEMENTED: "not_implemented",
    status.HTTP_503_SERVICE_UNAVAILABLE: "upstream_unavailable",
}

GENERIC_INTERNAL_MESSAGE = "Something went wrong. Please try again."

HTTP_422_UNPROCESSABLE = 422

def code_for_status(status_code: int) -> str:
    if status_code in _STATUS_CODE_NAMES:
        return _STATUS_CODE_NAMES[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    return "server_error"

def build_error_body(
    *,
    code: str,
    message: str,
    detail: Any,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    return {

        "detail": detail,
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
            "details": details,
        },
    }

def _response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    merged = dict(headers or {})
    request_id = get_request_id()
    if request_id:

        merged.setdefault(REQUEST_ID_HEADER, request_id)
    return JSONResponse(status_code=status_code, content=body, headers=merged)

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log = logger.bind(
        error_code=exc.code,
        status_code=exc.status_code,
        path=request.url.path,
    )
    if exc.status_code >= 500:
        log.error("Application error: {}", exc.message)
    else:
        log.info("Client error: {}", exc.message)

    return _response(
        exc.status_code,
        build_error_body(
            code=exc.code,
            message=exc.message,
            detail=exc.message,
            details=redact(exc.details) if exc.details is not None else None,
        ),
        headers=exc.headers,
    )

async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    message = detail if isinstance(detail, str) else code_for_status(exc.status_code)

    logger.bind(
        status_code=exc.status_code,
        path=request.url.path,
    ).info("HTTP error: {}", message)

    return _response(
        exc.status_code,
        build_error_body(
            code=code_for_status(exc.status_code),
            message=message,
            detail=detail,
        ),
        headers=getattr(exc, "headers", None),
    )

async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part != "body"]
        field_errors.append(
            {
                "field": ".".join(location) or "body",
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )

    logger.bind(
        status_code=HTTP_422_UNPROCESSABLE,
        path=request.url.path,
        invalid_fields=[fe["field"] for fe in field_errors],
    ).info("Request validation failed")

    return _response(
        HTTP_422_UNPROCESSABLE,
        build_error_body(
            code="validation_error",
            message="Some of the submitted values are not valid.",

            detail=_jsonable_errors(exc),
            details=field_errors,
        ),
    )

def _jsonable_errors(exc: RequestValidationError) -> Any:
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.bind(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
    ).opt(exception=exc).error("Unhandled exception")

    response = _response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        build_error_body(
            code="internal_error",
            message=GENERIC_INTERNAL_MESSAGE,
            detail=GENERIC_INTERNAL_MESSAGE,
        ),
    )

    return secure_response(response, request)

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

def upstream_error(operation: str, exc: Exception) -> UpstreamServiceError:
    logger.bind(operation=operation, exception_type=type(exc).__name__).opt(
        exception=exc
    ).error("Upstream operation failed: {}", operation)
    return UpstreamServiceError(
        f"{operation} is temporarily unavailable. Please try again.",
        code="upstream_unavailable",
    )

__all__ = [
    "AppError",
    "BadRequestError",
    "ConflictError",
    "ForbiddenError",
    "GENERIC_INTERNAL_MESSAGE",
    "InternalError",
    "NotFoundError",
    "RateLimitError",
    "UnauthorizedError",
    "UpstreamServiceError",
    "build_error_body",
    "code_for_status",
    "register_exception_handlers",
    "upstream_error",
]
