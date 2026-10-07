import json
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_agent_state_endpoint(client):
    """Verify that GET /api/agent/state returns state snapshot for dashboard."""
    response = client.get("/api/agent/state")
    assert response.status_code == 200
    data = response.json()

    assert "agent_status" in data
    assert "session_state" in data
    assert "conversation" in data
    assert "metrics" in data
    assert data["agent_status"] == "ONLINE"


def test_api_bookings_endpoint(client):
    """Verify that GET /api/bookings returns bookings array."""
    response = client.get("/api/bookings")
    assert response.status_code == 200
    data = response.json()
    assert "bookings" in data
    assert isinstance(data["bookings"], list)


def test_dashboard_websocket_mode(client):
    """Verify that /ws/media-stream supports dashboard clients via mode=dashboard."""
    with client.websocket_connect("/ws/media-stream?mode=dashboard") as ws:
        # Receive snapshot event on connect
        raw_msg = ws.receive_text()
        msg = json.loads(raw_msg)
        assert msg.get("event") == "snapshot"
        assert "agent_status" in msg.get("data", {})

        # Send heartbeat ping
        ws.send_text(json.dumps({"event": "ping"}))
        pong_raw = ws.receive_text()
        pong = json.loads(pong_raw)
        assert pong.get("event") == "pong"


def test_health_ready_includes_infrastructure_providers(client):
    """Verify that /health/ready includes RAG and Database in providers."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    providers = data.get("providers", {})
    assert "stt" in providers
    assert "llm" in providers
    assert "tts" in providers
    assert "rag" in providers
    assert "database" in providers


def test_api_pricing_currencies_endpoint(client):
    """Verify that GET /api/pricing/currencies returns currencies and country lists."""
    response = client.get("/api/pricing/currencies")
    assert response.status_code == 200
    data = response.json()
    assert data["base_currency"] == "USD"
    assert "currencies" in data
    assert "countries" in data
    assert "EUR" in data["currencies"]
    assert "INR" in data["currencies"]
    assert "GBP" in data["currencies"]
    assert "JPY" in data["currencies"]
    assert any(c["code"] == "US" for c in data["countries"])
    assert any(c["code"] == "IN" for c in data["countries"])
    assert any(c["code"] == "GB" for c in data["countries"])


def test_api_rooms_endpoint(client):
    """Verify that GET /api/rooms returns resort rooms with USD base rates."""
    response = client.get("/api/rooms")
    assert response.status_code == 200
    data = response.json()
    assert data["base_currency"] == "USD"
    assert "rooms" in data
    assert len(data["rooms"]) >= 3
    room_ids = [r["room_id"] for r in data["rooms"]]
    assert "villa-ocean-101" in room_ids
    assert "suite-deluxe-201" in room_ids
    assert "bungalow-garden-301" in room_ids


def test_api_pricing_calculate_dynamic_conversion(client):
    """Verify that POST /api/pricing/calculate keeps base USD and dynamically converts to target currency."""
    payload = {
        "room_id": "villa-ocean-101",
        "check_in": "2026-10-10",
        "check_out": "2026-10-14",
        "currency": "EUR",
        "country": "FR",
        "add_ons": ["breakfast"]
    }
    response = client.post("/api/pricing/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["currency"] == "EUR"
    assert data["base_pricing_usd"]["currency"] == "USD"
    assert data["base_pricing_usd"]["total_price"] > 0
    assert data["converted_pricing"]["currency"] == "EUR"
    assert data["converted_pricing"]["total_price"] > 0
    assert "exchange_rate" in data
    assert data["exchange_rate"] == 0.92
    assert "€" in data["converted_pricing"]["total_formatted"]


def test_api_conversation_clear_endpoint(client):
    """Verify that POST /api/conversation/clear completely resets conversation without touching bookings or DB."""
    from app.orchestrator.broadcaster import event_broadcaster
    import asyncio
    
    # 1. Start from clean state and populate mock conversation, tools, and RAG state
    event_broadcaster.clear_conversation_sync()
    asyncio.run(event_broadcaster.notify_user_transcript("Hello test", is_final=True))
    asyncio.run(event_broadcaster.notify_agent_response("Welcome to Azure Paradise!", is_final=True))
    asyncio.run(event_broadcaster.notify_tool_call("check_availability", {"check_in": "2026-10-10"}, {"ok": True}, "completed"))
    asyncio.run(event_broadcaster.notify_rag_retrieval("spa hours", [{"content": "Spa is open 8am-8pm"}]))

    assert len(event_broadcaster.state["conversation"]) == 2
    assert event_broadcaster.state["current_tool"] is not None
    assert event_broadcaster.state["last_rag"] is not None
    assert event_broadcaster.state["metrics"]["total_turns"] >= 1

    # 2. Query bookings and rooms before clear
    bookings_before = client.get("/api/bookings").json().get("bookings", [])
    rooms_before = client.get("/api/rooms").json().get("rooms", [])

    # 3. Call clear endpoint
    response = client.post("/api/conversation/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    # 4. Assert broadcaster state is completely clean
    assert len(event_broadcaster.state["conversation"]) == 0
    assert event_broadcaster.state["current_tool"] is None
    assert event_broadcaster.state["last_rag"] is None
    assert event_broadcaster.state["metrics"]["total_turns"] == 0

    # 5. Assert GET /api/agent/state returns empty conversation (no stale state restored via polling)
    state_res = client.get("/api/agent/state")
    assert state_res.status_code == 200
    state_data = state_res.json()
    assert state_data["conversation"] == []
    assert state_data["current_tool"] is None
    assert state_data["last_rag"] is None
    assert state_data["metrics"]["total_turns"] == 0

    # 6. Assert DB bookings and rooms catalog remain completely untouched
    bookings_after = client.get("/api/bookings").json().get("bookings", [])
    rooms_after = client.get("/api/rooms").json().get("rooms", [])
    assert len(bookings_after) == len(bookings_before)
    assert len(rooms_after) == len(rooms_before)

    # 7. Test Idempotency: multiple clear calls are completely safe
    for _ in range(3):
        idem_res = client.post("/api/conversation/clear")
        assert idem_res.status_code == 200
        assert idem_res.json()["status"] == "ok"
        assert len(event_broadcaster.state["conversation"]) == 0


def test_websocket_reconnect_does_not_replay_cleared_conversation(client):
    """Verify that after clear, reconnecting or subscribing to WebSocket sends empty conversation."""
    from app.orchestrator.broadcaster import event_broadcaster
    import asyncio

    # Clean broadcaster, then add mock conversation and clear
    event_broadcaster.clear_conversation_sync()
    asyncio.run(event_broadcaster.notify_user_transcript("Old question", is_final=True))
    asyncio.run(event_broadcaster.notify_agent_response("Old answer", is_final=True))
    assert len(event_broadcaster.state["conversation"]) == 2


    # Clear conversation
    res = client.post("/api/conversation/clear")
    assert res.status_code == 200

    # Connect WebSocket client (simulating dashboard reconnect)
    with client.websocket_connect("/ws/media-stream?mode=dashboard") as ws:
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "snapshot"
        assert init_msg.get("data", {}).get("conversation") == []

        # Send subscribe to simulate polling/refresh
        ws.send_text(json.dumps({"event": "subscribe"}))
        sub_raw = ws.receive_text()
        sub_msg = json.loads(sub_raw)
        assert sub_msg.get("event") == "snapshot"
        assert sub_msg.get("data", {}).get("conversation") == []


def test_session_state_and_stt_transcript_reset():
    """Verify that SessionState and STT providers properly reset internal message arrays and transcript buffers."""
    from app.orchestrator.session import SessionState
    from app.stt.assemblyai import AssemblyAISTTProvider
    from app.stt.deepgram import DeepgramSTTProvider
    from app.stt.base import STTCallback

    # 1. Test SessionState reset
    sess = SessionState("call_test_123", "stream_test_123")
    sess.add_user_message("I'd like to book a Deluxe Sunset Suite for October 10 to 14 for 2 guests")
    sess.complete_assistant_turn("I have reserved that for you.")
    sess.check_in = "2026-10-10"
    sess.check_out = "2026-10-14"
    sess.selected_room_id = "suite-deluxe-201"
    sess.has_greeted = True
    assert len(sess.messages) > 1

    sess.reset_conversation()
    assert len(sess.messages) == 1
    assert sess.messages[0]["role"] == "system"
    assert sess.check_in is None
    assert sess.check_out is None
    assert sess.selected_room_id is None
    assert sess.has_greeted is False

    # 2. Test STT providers reset
    dummy_cb = STTCallback()
    aai = AssemblyAISTTProvider(dummy_cb)
    aai._last_interim_transcript = "partial hello"
    aai._last_final_transcript = "hello world"
    aai.reset()
    assert aai._last_interim_transcript is None
    assert aai._last_final_transcript is None

    dg = DeepgramSTTProvider(dummy_cb)
    dg._last_interim_transcript = "interim test"
    dg._last_final_transcript = "final test"
    dg.reset()
    assert dg._last_interim_transcript is None
    assert dg._last_final_transcript is None


