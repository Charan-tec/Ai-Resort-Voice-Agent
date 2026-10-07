import base64
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_browser_voice_websocket_lifecycle(client):
    """Verify that /ws/browser-voice establishes connection, receives connected event, handles ping and start."""
    with client.websocket_connect("/ws/browser-voice") as ws:
        # 1. Verify initial 'connected' event
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "connected"
        assert "session_id" in init_msg
        assert init_msg.get("state") == "IDLE"

        # 2. Ping / Pong
        ws.send_text(json.dumps({"event": "ping"}))
        pong_raw = ws.receive_text()
        pong = json.loads(pong_raw)
        assert pong.get("event") == "pong"

        # 3. Start Voice Session
        ws.send_text(json.dumps({"event": "start", "session_id": "test_browser_session_1"}))
        
        # Should receive session_state: LISTENING
        state_raw = ws.receive_text()
        state_msg = json.loads(state_raw)
        assert state_msg.get("event") == "session_state"
        assert state_msg.get("state") == "LISTENING"

        # 4. Stop voice session
        ws.send_text(json.dumps({"event": "stop"}))


def test_browser_voice_barge_in_and_audio_frame(client):
    """Verify that inbound audio and barge_in event can be processed without error."""
    with client.websocket_connect("/ws/browser-voice") as ws:
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "connected"

        # Start session
        ws.send_text(json.dumps({"event": "start", "session_id": "test_browser_session_2"}))
        state_raw = ws.receive_text()
        state_msg = json.loads(state_raw)
        assert state_msg.get("event") == "session_state"

        # Send a 20ms frame of 8kHz linear PCM silence (320 bytes)
        silence_pcm = b"\x00" * 320
        payload_b64 = base64.b64encode(silence_pcm).decode("ascii")
        ws.send_text(json.dumps({
            "event": "media",
            "media": {"payload": payload_b64},
            "format": "pcm16_8000"
        }))

        # Send browser barge_in event
        ws.send_text(json.dumps({"event": "barge_in"}))

        # Send stop
        ws.send_text(json.dumps({"event": "stop"}))


def test_browser_voice_clear_conversation_event(client):
    """Verify that clear_conversation event over WebSocket resets conversation and returns conversation_cleared."""
    with client.websocket_connect("/ws/browser-voice") as ws:
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "connected"

        # 1. Start voice session
        ws.send_text(json.dumps({"event": "start", "session_id": "test_browser_clear_session"}))
        state_raw = ws.receive_text()
        state_msg = json.loads(state_raw)
        assert state_msg.get("event") == "session_state"
        assert state_msg.get("state") == "LISTENING"

        # 2. Inject user transcript
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "What rooms are available for October 10?",
            "is_final": True
        }))

        # 3. Request conversation clear
        ws.send_text(json.dumps({"event": "clear_conversation"}))

        # 4. Check for conversation_cleared event response
        cleared_msg = None
        for _ in range(50):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("event") == "conversation_cleared":
                cleared_msg = data
                break

        assert cleared_msg is not None
        assert cleared_msg.get("event") == "conversation_cleared"

        # 5. Stop session
        ws.send_text(json.dumps({"event": "stop"}))


def test_browser_voice_starts_fresh_after_clear(client):
    """Verify that after clear, a new voice session starts completely fresh without old conversation."""
    from app.orchestrator.broadcaster import event_broadcaster
    import asyncio

    # Inject mock previous messages
    asyncio.run(event_broadcaster.notify_user_transcript("Previous turn 1", is_final=True))
    asyncio.run(event_broadcaster.notify_agent_response("Previous response 1", is_final=True))
    assert len(event_broadcaster.state["conversation"]) == 2

    # Clear via API
    clear_resp = client.post("/api/conversation/clear")
    assert clear_resp.status_code == 200
    assert len(event_broadcaster.state["conversation"]) == 0

    # Start a brand new browser voice session
    with client.websocket_connect("/ws/browser-voice") as ws:
        init_raw = ws.receive_text()
        assert json.loads(init_raw).get("event") == "connected"

        ws.send_text(json.dumps({"event": "start", "session_id": "test_fresh_start_session"}))
        state_raw = ws.receive_text()
        assert json.loads(state_raw).get("event") == "session_state"

        # Verify broadcaster does not have previous old conversation
        old_contents = [m.get("content", "") for m in event_broadcaster.state["conversation"]]
        assert not any("Previous turn 1" in c for c in old_contents)
        assert not any("Previous response 1" in c for c in old_contents)

        ws.send_text(json.dumps({"event": "stop"}))


@pytest.mark.asyncio
async def test_browser_outbound_pacer_buffering_and_gapless_chunking():
    """Verify BrowserOutboundPacer accumulates chunks without premature silence padding and pads only on turn_end."""
    from app.telephony.browser_websocket import BrowserOutboundPacer
    from app.telephony.codecs import PCM_BYTES_PER_FRAME

    sent_messages = []

    async def mock_send(msg: str):
        sent_messages.append(msg)

    pacer = BrowserOutboundPacer(stream_sid="test_stream", send_fn=mock_send)
    
    # Send non-aligned chunks (e.g. 100 bytes μ-law -> 200 bytes PCM)
    await pacer.enqueue_audio(b"\x80" * 100)
    assert pacer._queue.empty(), "Should not yield a frame yet because len is only 200 bytes < 320"

    # Send another 100 bytes μ-law -> 200 bytes PCM (total 400 bytes)
    await pacer.enqueue_audio(b"\x80" * 100)
    assert not pacer._queue.empty(), "Should have yielded exactly 1 frame of 320 bytes"
    
    item = pacer._queue.get_nowait()
    assert item["type"] == "audio"
    assert len(item["data"]) == PCM_BYTES_PER_FRAME
    assert item["is_last"] is False
    # 80 bytes PCM remaining in _pcm_buffer
    assert len(pacer._pcm_buffer) == 80

    # Mark turn end: should flush the remaining 80 bytes padded to 320 bytes
    pacer.mark_turn_end(turn_id=1)
    final_item = pacer._queue.get_nowait()
    assert final_item["type"] == "audio"
    assert len(final_item["data"]) == PCM_BYTES_PER_FRAME
    assert final_item["is_last"] is True
    assert len(pacer._pcm_buffer) == 0

    sentinel_item = pacer._queue.get_nowait()
    assert sentinel_item["type"] == "turn_end"



