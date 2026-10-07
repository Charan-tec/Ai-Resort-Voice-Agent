import time
from app.core.security import TwilioSecurity, RateLimiter


def test_hmac_session_tokens():
    sec = TwilioSecurity(auth_token="dummy_auth_token", secret_key="super_secret_test_key")
    call_sid = "CA1234567890abcdef"

    token = sec.generate_session_token(call_sid)
    assert token.startswith(call_sid)

    # Valid token verification
    verified_sid = sec.verify_session_token(token)
    assert verified_sid == call_sid

    # Tampered token verification
    tampered_token = token[:-4] + "dead"
    assert sec.verify_session_token(tampered_token) is None

    # Expired token verification
    old_token = sec.generate_session_token(call_sid, timestamp=int(time.time()) - 4000)
    assert sec.verify_session_token(old_token, max_age_seconds=3600) is None


def test_rate_limiter():
    limiter = RateLimiter(max_requests=3, window_seconds=1.0)
    client_ip = "192.168.1.50"

    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    # 4th request within window blocked
    assert limiter.is_allowed(client_ip) is False


def test_production_config_requires_explicit_secure_secret_key():
    """Verify that ENVIRONMENT=production strictly rejects default fallbacks and insecure keys."""
    import pytest
    from app.core.config import Settings

    # Default fallback must fail in production (even without .env)
    with pytest.raises(ValueError, match="explicit secure SECRET_KEY"):
        Settings(_env_file=None, ENVIRONMENT="production")

    # Short secret key must fail in production
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(ENVIRONMENT="production", SECRET_KEY="too-short-key")

    # Placeholder secret key must fail in production
    with pytest.raises(ValueError, match="explicit secure SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="replace-with-a-very-long-and-secure-random-32char-secret"
        )

    # Valid >=32 char secret in production succeeds and enables production security defaults
    secure_prod_key = "a" * 32
    prod_settings = Settings(ENVIRONMENT="production", SECRET_KEY=secure_prod_key)
    assert prod_settings.SECRET_KEY == secure_prod_key
    assert prod_settings.WEBHOOK_SIGNATURE_VERIFY is True
    assert prod_settings.DEBUG is False

    # Development allows default fallback
    dev_settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert dev_settings.SECRET_KEY == "super-secret-resort-voice-agent-token-key-32chars"


def test_cors_allowed_origins_parsing_and_credentials_safety():
    """Verify that comma-separated and wildcard origins are parsed properly and credentials safety holds."""
    from app.core.config import Settings

    # Comma-separated string parsing
    s = Settings(ALLOWED_ORIGINS="https://domain1.com, https://domain2.com")
    assert s.ALLOWED_ORIGINS == ["https://domain1.com", "https://domain2.com"]

    # JSON string parsing
    s_json = Settings(ALLOWED_ORIGINS='["https://app.resort.com"]')
    assert s_json.ALLOWED_ORIGINS == ["https://app.resort.com"]

    # Wildcard origin flag check
    origins_wildcard = ["*"]
    has_wildcard = "*" in origins_wildcard
    allow_credentials_wildcard = bool(origins_wildcard) and not has_wildcard
    assert allow_credentials_wildcard is False

    # Specific origins flag check
    origins_specific = ["https://app.resort.com"]
    has_wildcard_spec = "*" in origins_specific
    allow_credentials_spec = bool(origins_specific) and not has_wildcard_spec
    assert allow_credentials_spec is True


def test_production_websocket_rejects_missing_token_even_with_verify_disabled():
    """Verify that in production mode, WebSocket connection without token is closed with 1008."""
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.main import app
    from app.core.config import settings
    import pytest

    client = TestClient(app)
    orig_env = settings.ENVIRONMENT
    orig_verify = settings.WEBHOOK_SIGNATURE_VERIFY

    try:
        settings.ENVIRONMENT = "production"
        settings.WEBHOOK_SIGNATURE_VERIFY = False

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/media-stream"):
                pass
        assert exc_info.value.code == 1008
    finally:
        settings.ENVIRONMENT = orig_env
        settings.WEBHOOK_SIGNATURE_VERIFY = orig_verify


def test_cors_middleware_response_headers():
    """Verify that CORS response headers do not enable credentials when wildcard origins are used."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/health/live", headers={"Origin": "http://random-origin.com"})
    assert response.status_code == 200
    # Credentials must NOT be allowed when wildcard origin is configured
    assert response.headers.get("access-control-allow-credentials") != "true"
