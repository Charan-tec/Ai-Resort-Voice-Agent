import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_readiness_probe_does_not_expose_secrets(client):
    """Verify that /health/ready returns diagnostic information without exposing any secret values."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    # Verify structural sections
    assert "status" in data
    assert "ready_for_real_calls" in data
    assert "public_url" in data
    assert "telephony" in data
    assert "providers" in data
    assert "missing_requirements" in data

    # Verify that no API key or token strings appear anywhere in the JSON response
    response_text = response.text.lower()
    for sensitive_word in ("sk-", "secret_key", "authtoken", "auth_token_value", "password"):
        assert sensitive_word not in response_text


def test_readiness_probe_detects_localhost_warning(client, monkeypatch):
    """Verify that /health/ready flags localhost or example.com as not public."""
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000")

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    assert data["public_url"]["is_public"] is False
    assert data["ready_for_real_calls"] is False
    assert any("PUBLIC_BASE_URL" in msg for msg in data["missing_requirements"])


def test_readiness_probe_reports_ready_when_configured(client, monkeypatch):
    """Verify that /health/ready reports status: ready when all prerequisites are met."""
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://real-resort-tunnel.ngrok-free.app")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC11223344556677889900aabbccddeeff")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "11223344556677889900aabbccddeeff")
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+18085559876")
    monkeypatch.setattr(settings, "ASSEMBLYAI_API_KEY", "real_test_aai_key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real_test_gemini_key")
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "real_test_elevenlabs_key")

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ready"
    assert data["ready_for_real_calls"] is True
    assert data["public_url"]["is_public"] is True
    assert data["public_url"]["is_https"] is True
    assert len(data["missing_requirements"]) == 0
