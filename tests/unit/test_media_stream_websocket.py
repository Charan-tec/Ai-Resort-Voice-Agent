import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.core.config import settings
from app.core.security import twilio_security
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_websocket_connection_with_valid_hmac_token(client):
    """Verify that a WebSocket connection with a valid HMAC session token connects cleanly."""
    call_sid = "CA_valid_token_test_123"
    valid_token = twilio_security.generate_session_token(call_sid)

    with client.websocket_connect(f"/ws/media-stream?token={valid_token}") as ws:
        # Send connected event
        ws.send_text(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))

        # Send stop event to terminate stream loop cleanly
        ws.send_text(json.dumps({"event": "stop", "streamSid": "MZ_test_stream"}))


def test_websocket_connection_rejects_invalid_token_when_verification_enabled(client, monkeypatch):
    """Verify that an invalid HMAC session token is rejected when signature verification is enabled."""
    monkeypatch.setattr(settings, "WEBHOOK_SIGNATURE_VERIFY", True)

    invalid_token = "CA_fake_call_sid:12345678:invalid_hmac_signature"

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/media-stream?token={invalid_token}"):
            pass

    assert exc_info.value.code == 1008


def test_websocket_accepts_connection_without_token_in_development(client, monkeypatch):
    """Verify that local test tools/simulators without tokens are permitted in development mode."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "WEBHOOK_SIGNATURE_VERIFY", False)

    with client.websocket_connect("/ws/media-stream") as ws:
        ws.send_text(json.dumps({"event": "connected", "protocol": "Call"}))
        ws.send_text(json.dumps({"event": "stop", "streamSid": "MZ_test"}))


def test_websocket_protocol_lifecycle(client):
    """Verify standard Twilio protocol messages: connected, start, media, mark, stop."""
    call_sid = "CA_protocol_lifecycle_call"
    token = twilio_security.generate_session_token(call_sid)

    with client.websocket_connect(f"/ws/media-stream?token={token}") as ws:
        # 1. Connected
        ws.send_text(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))

        # 2. Start
        start_payload = {
            "event": "start",
            "streamSid": "MZ_lifecycle_stream",
            "start": {
                "streamSid": "MZ_lifecycle_stream",
                "callSid": call_sid,
                "accountSid": "AC_test_account",
                "customParameters": {
                    "simulated_utterance": "Hello resort agent"
                }
            }
        }
        ws.send_text(json.dumps(start_payload))

        # 3. Mark ACK
        ws.send_text(json.dumps({
            "event": "mark",
            "streamSid": "MZ_lifecycle_stream",
            "mark": {"name": "test_mark_1"}
        }))

        # 4. Stop
        ws.send_text(json.dumps({
            "event": "stop",
            "streamSid": "MZ_lifecycle_stream",
            "stop": {"callSid": call_sid}
        }))
