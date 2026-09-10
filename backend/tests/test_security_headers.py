import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_auth import client

from core.security_headers import (
    CONTENT_TYPE_OPTIONS_HEADER,
    COOP_HEADER,
    CORP_HEADER,
    CSP_HEADER,
    DEFAULT_CONTENT_TYPE_OPTIONS,
    DEFAULT_FRAME_OPTIONS,
    DEFAULT_REFERRER_POLICY,
    FRAME_OPTIONS_HEADER,
    HSTS_HEADER,
    PERMISSIONS_POLICY_HEADER,
    REFERRER_POLICY_HEADER,
    SecurityHeadersMiddleware,
    build_header_policy,
    resolve_scheme,
)

ALWAYS_PRESENT = (
    CONTENT_TYPE_OPTIONS_HEADER,
    FRAME_OPTIONS_HEADER,
    REFERRER_POLICY_HEADER,
    PERMISSIONS_POLICY_HEADER,
    CSP_HEADER,
    COOP_HEADER,
    CORP_HEADER,
)

def _app_with(**middleware_kwargs) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, **middleware_kwargs)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise HTTPException(status_code=418, detail="teapot")

    @app.get("/crash")
    async def crash():
        raise RuntimeError("unhandled")

    @app.get("/own-csp")
    async def own_csp():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"ok": True},
            headers={"Content-Security-Policy": "default-src 'none'"},
        )

    return TestClient(app, raise_server_exceptions=False)

@pytest.mark.parametrize("header", ALWAYS_PRESENT)
def test_header_present_on_real_app_response(header):
    response = client.get("/api/v1/health")
    assert header in response.headers, f"{header} missing from /health"

def test_nosniff_and_frame_options_have_the_expected_values():
    response = client.get("/api/v1/health")
    assert response.headers[CONTENT_TYPE_OPTIONS_HEADER] == DEFAULT_CONTENT_TYPE_OPTIONS
    assert response.headers[FRAME_OPTIONS_HEADER] == DEFAULT_FRAME_OPTIONS
    assert response.headers[REFERRER_POLICY_HEADER] == DEFAULT_REFERRER_POLICY

def test_csp_denies_framing_and_object_embedding():
    csp = client.get("/api/v1/health").headers[CSP_HEADER]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "default-src 'self'" in csp

def test_headers_are_present_on_the_root_route():
    response = client.get("/")
    assert response.status_code == 200
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_server_header_is_not_advertised():
    assert "server" not in {k.lower() for k in client.get("/api/v1/health").headers}

def test_hsts_absent_over_plaintext():
    assert HSTS_HEADER not in client.get("/api/v1/health").headers

def test_hsts_present_when_the_proxy_reports_https():
    response = client.get(
        "/api/v1/health", headers={"X-Forwarded-Proto": "https"}
    )
    assert HSTS_HEADER in response.headers
    assert "max-age=" in response.headers[HSTS_HEADER]
    assert "includeSubDomains" in response.headers[HSTS_HEADER]

def test_hsts_absent_when_the_proxy_reports_http():
    response = client.get("/api/v1/health", headers={"X-Forwarded-Proto": "http"})
    assert HSTS_HEADER not in response.headers

def test_forwarded_proto_chain_uses_the_client_facing_hop():
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "http", "headers": []}
    headers = Headers({"x-forwarded-proto": "https, http"})
    assert resolve_scheme(scope, headers) == "https"

def test_scheme_falls_back_to_the_scope_when_unproxied():
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "https", "headers": []}
    assert resolve_scheme(scope, Headers({})) == "https"

def test_forwarded_proto_is_case_insensitive():
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "http", "headers": []}
    assert resolve_scheme(scope, Headers({"x-forwarded-proto": "HTTPS"})) == "https"

def test_headers_present_on_a_404():
    response = client.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_headers_present_on_a_handled_http_exception():
    response = _app_with().get("/boom")
    assert response.status_code == 418
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_headers_present_on_an_unhandled_exception():
    probe_app = FastAPI()

    @probe_app.get("/probe-crash")
    async def probe_crash():
        raise RuntimeError("unhandled")

    from core.errors import register_exception_handlers
    from core.middleware import RequestContextMiddleware

    probe_app.add_middleware(RequestContextMiddleware)
    probe_app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(probe_app)

    response = TestClient(probe_app, raise_server_exceptions=False).get(
        "/probe-crash"
    )
    assert response.status_code == 500
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_headers_present_on_a_validation_error():
    response = client.get("/api/v1/cycle/u1/history?limit=-1")
    assert response.status_code in (401, 403, 422)
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_headers_present_on_an_unauthenticated_401():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    for header in ALWAYS_PRESENT:
        assert header in response.headers

def test_a_route_that_sets_its_own_csp_keeps_it():
    response = _app_with().get("/own-csp")
    assert response.headers[CSP_HEADER] == "default-src 'none'"

    assert response.headers[CONTENT_TYPE_OPTIONS_HEADER] == "nosniff"

def test_a_header_can_be_disabled_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECURITY_CSP", "off")
    policy = build_header_policy()
    assert CSP_HEADER not in policy

    assert CONTENT_TYPE_OPTIONS_HEADER in policy

@pytest.mark.parametrize("disabled", ["", "off", "none", "false", "0", "  OFF  "])
def test_all_disable_spellings_are_honoured(monkeypatch, disabled):
    monkeypatch.setenv("SECURITY_FRAME_OPTIONS", disabled)
    assert FRAME_OPTIONS_HEADER not in build_header_policy()

def test_a_header_value_can_be_replaced_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECURITY_REFERRER_POLICY", "no-referrer")
    assert build_header_policy()[REFERRER_POLICY_HEADER] == "no-referrer"

def test_hsts_can_be_disabled_explicitly():
    response = _app_with(hsts="off").get(
        "/ping", headers={"X-Forwarded-Proto": "https"}
    )
    assert HSTS_HEADER not in response.headers

def test_excluded_paths_are_left_alone():
    response = _app_with(exclude_paths={"/ping"}).get("/ping")
    assert CSP_HEADER not in response.headers

def test_server_header_stripping_is_applied_and_can_be_turned_off():
    from starlette.datastructures import MutableHeaders

    def _headers_with_server():
        headers = MutableHeaders()
        headers["server"] = "uvicorn"
        return headers

    stripping = SecurityHeadersMiddleware(app=None, strip_server_header=True)
    headers = _headers_with_server()
    stripping.apply(headers, scheme="https")
    assert "server" not in headers

    keeping = SecurityHeadersMiddleware(app=None, strip_server_header=False)
    headers = _headers_with_server()
    keeping.apply(headers, scheme="https")
    assert headers["server"] == "uvicorn"

def test_request_id_still_reaches_the_client():
    response = client.get("/api/v1/health")
    assert response.headers.get("x-request-id")

def test_cors_preflight_is_not_broken():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin")

def test_cors_exposed_headers_are_unchanged():
    response = client.get(
        "/api/v1/health", headers={"Origin": "http://localhost:5173"}
    )
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in exposed
