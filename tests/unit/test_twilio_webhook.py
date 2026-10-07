import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.security import twilio_security
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_incoming_call_webhook_post_twiml_generation(client):
    """Verify that POST /telephony/incoming-call returns valid TwiML with Connect and Stream."""
    payload = {
        "CallSid": "CA_test_webhook_call_123",
        "From": "+15551234567",
        "To": "+18005559999",
    }
    response = client.post("/telephony/incoming-call", data=payload)
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]

    # Parse TwiML XML
    root = ET.fromstring(response.text)
    assert root.tag == "Response"

    connect_elem = root.find("Connect")
    assert connect_elem is not None

    stream_elem = connect_elem.find("Stream")
    assert stream_elem is not None

    stream_url = stream_elem.attrib.get("url", "")
    assert "ws" in stream_url
    assert "/ws/media-stream" in stream_url
    assert "token=" in stream_url

    # Verify custom parameters
    params = {p.attrib.get("name"): p.attrib.get("value") for p in stream_elem.findall("Parameter")}
    assert params.get("callSid") == "CA_test_webhook_call_123"
    assert params.get("callerNumber") == "+15551234567"


def test_incoming_call_webhook_get_support(client):
    """Verify that GET /telephony/incoming-call is supported as a fallback."""
    response = client.get("/telephony/incoming-call?CallSid=CA_test_get_123&From=+15559876543")
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]

    root = ET.fromstring(response.text)
    connect_elem = root.find("Connect")
    assert connect_elem is not None
    stream_elem = connect_elem.find("Stream")
    assert stream_elem is not None
    assert "CA_test_get_123" in stream_elem.attrib.get("url", "")


def test_incoming_call_webhook_forwarded_host_detection(client, monkeypatch):
    """Verify that X-Forwarded-Host and X-Forwarded-Proto are used when configured URL is localhost."""
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000")

    headers = {
        "X-Forwarded-Proto": "https",
        "X-Forwarded-Host": "my-resort-tunnel.ngrok-free.app",
    }
    payload = {"CallSid": "CA_tunnel_test_123", "From": "+15550001111"}
    response = client.post("/telephony/incoming-call", data=payload, headers=headers)
    assert response.status_code == 200

    root = ET.fromstring(response.text)
    stream_elem = root.find("Connect").find("Stream")
    stream_url = stream_elem.attrib.get("url", "")

    assert stream_url.startswith("wss://my-resort-tunnel.ngrok-free.app/ws/media-stream")


def test_incoming_call_signature_validation_failure(client, monkeypatch):
    """Verify that invalid Twilio signature returns 403 when signature verification is enabled."""
    monkeypatch.setattr(settings, "WEBHOOK_SIGNATURE_VERIFY", True)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "valid_auth_token_for_test")

    headers = {
        "X-Twilio-Signature": "invalid_forged_signature_12345"
    }
    payload = {"CallSid": "CA_unauthorized_call", "From": "+15559998888"}
    response = client.post("/telephony/incoming-call", data=payload, headers=headers)
    assert response.status_code == 403
    assert "Unauthorized" in response.text


def test_incoming_call_signature_validation_success(client, monkeypatch):
    """Verify that valid Twilio signature passes verification when enabled."""
    monkeypatch.setattr(settings, "WEBHOOK_SIGNATURE_VERIFY", True)
    test_auth_token = "secret_auth_token_for_unit_test"
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", test_auth_token)
    monkeypatch.setattr(twilio_security, "auth_token", test_auth_token)
    monkeypatch.setattr(twilio_security, "validator", twilio_security.validator.__class__(test_auth_token))

    url = "http://testserver/telephony/incoming-call"
    params = {"CallSid": "CA_valid_call_789", "From": "+15554443322"}

    # Generate genuine Twilio signature using the validator
    valid_signature = twilio_security.validator.compute_signature(url, params)

    headers = {"X-Twilio-Signature": valid_signature}
    response = client.post("/telephony/incoming-call", data=params, headers=headers)
    assert response.status_code == 200
    assert "<Response>" in response.text
