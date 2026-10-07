import asyncio
import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app
from app.telephony.codecs import PCM_BYTES_PER_FRAME, ULAW_BYTES_PER_FRAME, pcm_to_ulaw, ulaw_to_pcm
from app.telephony.exotel_adapter import ExotelMediaAdapter, ExotelOutboundPacer
from app.services.exotel_service import ExotelService


@pytest.fixture
def client():
    return TestClient(app)


# ------------------------------------------------------------------------------
# 1. ExotelOutboundPacer Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exotel_pacer_enqueue_converts_ulaw_to_pcm():
    """Verify outbound pacer converts μ-law from TTS into 320-byte linear16 PCM frames."""
    sent_messages = []

    async def dummy_send(msg: str):
        sent_messages.append(json.loads(msg))

    pacer = ExotelOutboundPacer(
        stream_sid="exo_test_stream_01",
        send_fn=dummy_send,
        frame_interval_sec=0.001,
        mark_interval_frames=5
    )
    pacer.start()

    # Enqueue 320 bytes of μ-law (2 frames of 160 bytes -> 2 frames of 320 bytes PCM = 640 bytes PCM)
    sample_ulaw = b"\xff" * 320
    await pacer.enqueue_audio(sample_ulaw, metadata={"text": "Hello guest"})
    pacer.mark_turn_end()

    # Wait for pacing loop to deliver frames
    await asyncio.sleep(0.05)
    await pacer.stop()

    media_events = [m for m in sent_messages if m.get("event") == "media"]
    assert len(media_events) == 2, f"Expected 2 media frames, got {len(media_events)}"

    # Check payload is 320 bytes of linear PCM
    payload_b64 = media_events[0]["media"]["payload"]
    pcm_bytes = base64.b64decode(payload_b64)
    assert len(pcm_bytes) == PCM_BYTES_PER_FRAME
    assert media_events[0]["stream_sid"] == "exo_test_stream_01"


@pytest.mark.asyncio
async def test_exotel_pacer_flush_sends_clear():
    """Verify flush drops remaining frames and immediately sends Exotel clear event."""
    sent_messages = []

    async def dummy_send(msg: str):
        sent_messages.append(json.loads(msg))

    pacer = ExotelOutboundPacer(
        stream_sid="exo_flush_stream",
        send_fn=dummy_send,
        frame_interval_sec=0.05  # Slow pacing to test flush
    )
    pacer.start()

    # Enqueue multiple frames
    sample_ulaw = b"\xff" * 1600  # 10 frames
    await pacer.enqueue_audio(sample_ulaw)

    # Immediately flush
    await pacer.flush()
    await pacer.stop()

    clear_events = [m for m in sent_messages if m.get("event") == "clear"]
    assert len(clear_events) == 1
    assert clear_events[0]["stream_sid"] == "exo_flush_stream"
    assert clear_events[0]["streamSid"] == "exo_flush_stream"


@pytest.mark.asyncio
async def test_exotel_pacer_mark_ack_tracking():
    """Verify Exotel mark acknowledgments are tracked accurately."""
    pacer = ExotelOutboundPacer(stream_sid="exo_mark_test", send_fn=AsyncMock())
    pacer._sent_marks["exotel_mark_1"] = {"text": "Welcome to resort", "frame_count": 5}

    pacer.handle_mark_ack("exotel_mark_1")
    last_mark, meta = pacer.get_last_acked()

    assert last_mark == "exotel_mark_1"
    assert meta["text"] == "Welcome to resort"


# ------------------------------------------------------------------------------
# 2. ExotelMediaAdapter Inbound Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exotel_media_adapter_inbound_converts_pcm_to_ulaw():
    """Verify inbound 8kHz PCM16 audio is sliced into 320-byte frames and converted to μ-law."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.handle_inbound_audio = AsyncMock()

    mock_stt = MagicMock()
    mock_stt.send_audio = AsyncMock()

    pacer = ExotelOutboundPacer(stream_sid="exo_adapter_stream", send_fn=AsyncMock())
    adapter = ExotelMediaAdapter(
        stream_sid="exo_adapter_stream",
        pacer=pacer,
        orchestrator=mock_orchestrator,
        stt=mock_stt
    )

    # Send 640 bytes of PCM16 (exactly two 320-byte 20ms frames)
    pcm_audio = b"\x10\x00" * 320
    b64_payload = base64.b64encode(pcm_audio).decode("ascii")

    await adapter.handle_inbound_media_payload(b64_payload)

    # Should have dispatched 2 frames to both orchestrator (EnergyGate) and STT
    assert mock_orchestrator.handle_inbound_audio.call_count == 2
    assert mock_stt.send_audio.call_count == 2

    # Each frame received by orchestrator must be 160 bytes of μ-law
    received_frame = mock_orchestrator.handle_inbound_audio.call_args_list[0][0][0]
    assert len(received_frame) == ULAW_BYTES_PER_FRAME


# ------------------------------------------------------------------------------
# 3. Exotel HTTP POST/GET Endpoints Tests
# ------------------------------------------------------------------------------

def test_exotel_http_get_info(client):
    """Verify GET /ws/exotel-media returns endpoint metadata."""
    response = client.get("/ws/exotel-media")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "exotel-agentstream"
    assert "8kHz mono linear16 PCM" in data["audio_format"]


def test_exotel_http_post_handshake_json(client):
    """Verify POST /ws/exotel-media returns stream connection configuration as JSON."""
    response = client.post("/ws/exotel-media", json={"CallSid": "exo_call_123", "From": "+919876543210"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["StreamType"] == "bidirectional"
    assert "/ws/exotel-media" in data["StreamUrl"]


def test_exotel_http_post_handshake_xml(client):
    """Verify POST /ws/exotel-media returns ExoML when requested."""
    response = client.post(
        "/ws/exotel-media",
        data={"CallSid": "exo_call_456", "From": "+919876543210"},
        headers={"Accept": "application/xml"}
    )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Stream" in response.text
    assert 'type="bidirectional"' in response.text


# ------------------------------------------------------------------------------
# 4. Exotel WebSocket (/ws/exotel-media) Tests
# ------------------------------------------------------------------------------

def test_exotel_websocket_lifecycle(client):
    """
    Test full Exotel AgentStream WebSocket protocol lifecycle:
    connected -> start -> media -> mark -> clear -> stop.
    """
    with client.websocket_connect("/ws/exotel-media") as ws:
        # 1. Send connected event
        ws.send_text(json.dumps({
            "event": "connected",
            "protocol": "AgentStream",
            "version": "1.0.0"
        }))

        # 2. Send start event with simulated_utterance for deterministic test
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "stream_exo_unit_01",
            "start": {
                "stream_sid": "stream_exo_unit_01",
                "call_sid": "call_exo_unit_01",
                "from": "+919876543210",
                "to": "+918000000000",
                "custom_parameters": {
                    "simulated_utterance": "I want to check room availability"
                }
            }
        }))

        # 3. Send media event (8kHz linear16 PCM frame)
        pcm_frame = b"\x00\x00" * 160  # 320 bytes PCM silence
        ws.send_text(json.dumps({
            "event": "media",
            "stream_sid": "stream_exo_unit_01",
            "media": {
                "payload": base64.b64encode(pcm_frame).decode("ascii")
            }
        }))

        # 4. Send mark event
        ws.send_text(json.dumps({
            "event": "mark",
            "stream_sid": "stream_exo_unit_01",
            "mark": {
                "name": "exotel_mark_1"
            }
        }))

        # 5. Send clear event
        ws.send_text(json.dumps({
            "event": "clear",
            "stream_sid": "stream_exo_unit_01"
        }))

        # 6. Send stop event
        ws.send_text(json.dumps({
            "event": "stop",
            "stream_sid": "stream_exo_unit_01"
        }))


# ------------------------------------------------------------------------------
# 5. Exotel Outbound Call API Service Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exotel_service_outbound_call_validation():
    """Verify validation when Exotel credentials or caller ID are missing."""
    service = ExotelService()

    # Test with unconfigured settings
    with patch.object(settings, "EXOTEL_API_KEY", None):
        res = await service.initiate_outbound_call(to_phone="+919876543210")
        assert res["success"] is False
        assert "not fully configured" in res["error"]

    # Test with credentials but missing EXOTEL_CALLER_ID
    with patch.object(settings, "EXOTEL_API_KEY", "test_key"), \
         patch.object(settings, "EXOTEL_API_TOKEN", "test_token"), \
         patch.object(settings, "EXOTEL_ACCOUNT_SID", "test_sid"), \
         patch.object(settings, "EXOTEL_CALLER_ID", None):
        res = await service.initiate_outbound_call(to_phone="+919876543210")
        assert res["success"] is False
        assert "EXOTEL_CALLER_ID is required" in res["error"]


@pytest.mark.asyncio
async def test_exotel_service_outbound_call_success():
    """Verify successful Exotel outbound call POST dispatch and parameter formatting."""
    service = ExotelService()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.text = '{"Call": {"Sid": "call_exo_mock_999", "Status": "in-progress"}}'
    mock_resp.json.return_value = {"Call": {"Sid": "call_exo_mock_999", "Status": "in-progress"}}

    with patch.object(settings, "EXOTEL_API_KEY", "test_key"), \
         patch.object(settings, "EXOTEL_API_TOKEN", "test_token"), \
         patch.object(settings, "EXOTEL_ACCOUNT_SID", "test_account"), \
         patch.object(settings, "EXOTEL_CALLER_ID", "+918000000000"), \
         patch.object(settings, "EXOTEL_PUBLIC_WSS_URL", "wss://tunnel.ngrok-free.app/ws/exotel-media"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:

        mock_post.return_value = mock_resp

        result = await service.initiate_outbound_call(
            to_phone="+919876543210"
        )

        assert result["success"] is True
        assert result["call_sid"] == "call_exo_mock_999"

        # Check call arguments
        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        data = call_kwargs["data"]

        assert data["From"] == "+919876543210"
        assert data["CallerId"] == "+918000000000"
        assert data["StreamUrl"] == "wss://tunnel.ngrok-free.app/ws/exotel-media"
        assert data["StreamType"] == "bidirectional"


def test_api_exotel_call_endpoint(client):
    """Verify POST /api/exotel/call endpoint dispatches outbound call."""
    with patch("app.services.exotel_service.exotel_service.initiate_outbound_call", new_callable=AsyncMock) as mock_init:
        mock_init.return_value = {
            "success": True,
            "status_code": 200,
            "call_sid": "exo_call_111",
            "data": {"Sid": "exo_call_111"}
        }

        resp = client.post("/api/exotel/call", json={"to": "+919876543210"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["call_sid"] == "exo_call_111"
