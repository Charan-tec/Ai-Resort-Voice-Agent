import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.orchestrator.turn_manager import TurnManager, TurnState
from app.orchestrator.broadcaster import EventBroadcaster
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.orchestrator.session import SessionState
from fastapi.testclient import TestClient
from app.main import app


# ---------------------------------------------------------------------------
# Test A: Multiple partial transcripts -> exactly ONE final user message
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multiple_partial_transcripts_produce_exactly_one_final():
    """Requirement A: Multiple partial transcripts must update the same turn without committing,

    and when final arrives, commit exactly ONE message.
    """
    tm = TurnManager(session_id="test_turn_a")
    tm.set_state(TurnState.LISTENING)
    broadcaster = EventBroadcaster()

    # Turn starts
    tid = tm.start_user_turn()
    assert tid.startswith("turn_")

    # Series of evolving partial transcripts (e.g. from screen recording example)
    partials = [
        "availability or not",
        "availability or not and dining sepa",
        "availability or not and dining sepa and how much rent for that"
    ]
    for p in partials:
        p_tid = tm.handle_user_speech_partial(p, turn_id=tid)
        assert p_tid == tid
        # Broadcaster receives partial with is_final=False
        await broadcaster.notify_user_transcript(p, is_final=False, turn_id=p_tid)

    # Broadcaster state must NOT have committed these partials as permanent messages
    assert len(broadcaster.state["conversation"]) == 0

    # Final refined transcript arrives
    final_text = "availability how much rent for that"
    committed = await tm.handle_user_speech_final(final_text, turn_id=tid)
    assert committed is True
    assert tm.last_committed_turn_id == tid

    # Commit the single final message to broadcaster
    await broadcaster.notify_user_transcript(final_text, is_final=True, turn_id=tid)

    # Exactly ONE permanent user message committed
    assert len(broadcaster.state["conversation"]) == 1
    assert broadcaster.state["conversation"][0]["role"] == "user"
    assert broadcaster.state["conversation"][0]["content"] == final_text
    assert broadcaster.state["conversation"][0]["turn_id"] == tid


# ---------------------------------------------------------------------------
# Test B: Partial + final -> exactly ONE committed message
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partial_then_final_single_committed():
    """Requirement B: Partial transcript arrives, followed by final transcript.

    Result must be exactly ONE committed message.
    """
    tm = TurnManager(session_id="test_turn_b")
    tm.set_state(TurnState.LISTENING)
    broadcaster = EventBroadcaster()

    tid = tm.start_user_turn()
    tm.handle_user_speech_partial("What is the check-in", turn_id=tid)
    await broadcaster.notify_user_transcript("What is the check-in", is_final=False, turn_id=tid)

    assert len(broadcaster.state["conversation"]) == 0

    committed = await tm.handle_user_speech_final("What is the check-in time?", turn_id=tid)
    assert committed is True
    await broadcaster.notify_user_transcript("What is the check-in time?", is_final=True, turn_id=tid)

    assert len(broadcaster.state["conversation"]) == 1
    assert broadcaster.state["conversation"][0]["content"] == "What is the check-in time?"


# ---------------------------------------------------------------------------
# Test C: Duplicate final event -> ignored
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_final_event_ignored():
    """Requirement C: If the exact same final event arrives twice, ignore the duplicate."""
    tm = TurnManager(session_id="test_turn_c")
    tm.set_state(TurnState.LISTENING)

    tid = tm.start_user_turn()
    committed_1 = await tm.handle_user_speech_final("Do you allow pets?", turn_id=tid)
    assert committed_1 is True

    # Same final text received again immediately
    committed_2 = await tm.handle_user_speech_final("Do you allow pets?", turn_id=tid)
    assert committed_2 is False


# ---------------------------------------------------------------------------
# Test D: Same turn_id received twice -> processed once
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_same_turn_id_processed_once():
    """Requirement D: The orchestrator and TurnManager must process a turn_id only once."""
    tm = TurnManager(session_id="test_turn_d")
    tm.set_state(TurnState.LISTENING)

    tid = "turn_fixed_test_123"
    committed_1 = await tm.handle_user_speech_final("How much is the suite?", turn_id=tid)
    assert committed_1 is True

    # Same turn_id with slightly different casing or timing
    committed_2 = await tm.handle_user_speech_final("how much is the suite?", turn_id=tid)
    assert committed_2 is False


# ---------------------------------------------------------------------------
# Test E: Two genuinely different user turns -> both preserved
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_genuinely_different_turns_preserved():
    """Requirement E: Two genuinely different user sentences are both preserved and committed."""
    tm = TurnManager(session_id="test_turn_e")
    tm.set_state(TurnState.LISTENING)
    broadcaster = EventBroadcaster()

    # Turn 1
    tid1 = tm.start_user_turn()
    committed_1 = await tm.handle_user_speech_final("What time is check-in?", turn_id=tid1)
    assert committed_1 is True
    await broadcaster.notify_user_transcript("What time is check-in?", is_final=True, turn_id=tid1)

    # Agent responds and turn finishes
    tm.set_state(TurnState.SPEAKING)
    tm.set_state(TurnState.LISTENING)
    await broadcaster.notify_agent_response("Check-in is at 3:00 PM.", mark_id="m1", is_final=True, turn_id=tid1)

    # Turn 2
    tid2 = tm.start_user_turn()
    assert tid2 != tid1
    committed_2 = await tm.handle_user_speech_final("Is breakfast included?", turn_id=tid2)
    assert committed_2 is True
    await broadcaster.notify_user_transcript("Is breakfast included?", is_final=True, turn_id=tid2)

    assert len(broadcaster.state["conversation"]) == 3
    assert broadcaster.state["conversation"][0]["content"] == "What time is check-in?"
    assert broadcaster.state["conversation"][1]["content"] == "Check-in is at 3:00 PM."
    assert broadcaster.state["conversation"][2]["content"] == "Is breakfast included?"


# ---------------------------------------------------------------------------
# Test F: Agent receives only final transcript
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_agent_receives_only_final_transcript():
    """Requirement F: The orchestrator must never dispatch partial transcripts to the LLM agent."""
    pacer_mock = MagicMock()
    pacer_mock.flush = AsyncMock()
    pacer_mock.start_turn = MagicMock()
    pacer_mock.mark_turn_end = MagicMock()

    orchestrator = VoiceAgentOrchestrator(
        call_sid="test_orch_turn_f",
        stream_sid="test_stream_turn_f",
        pacer=pacer_mock
    )
    orchestrator.turn_manager.set_state(TurnState.LISTENING)

    # Mock _stream_llm_and_tts
    with patch.object(orchestrator, "_stream_llm_and_tts", new_callable=AsyncMock) as mock_llm:
        # 1. Send interim transcripts
        await orchestrator.handle_interim_transcript("availability or not")
        await orchestrator.handle_interim_transcript("availability or not and dining sepa")
        await orchestrator.handle_interim_transcript("availability or not and dining sepa and how much")

        # LLM streaming should NOT have been called for interim transcripts
        assert mock_llm.call_count == 0

        # 2. Send final transcript
        committed = await orchestrator.handle_final_transcript("availability how much rent for that")
        assert committed is True

        # Wait briefly for background task execution
        await asyncio.sleep(0.05)

        # LLM streaming must be called exactly once
        assert mock_llm.call_count == 1
        # Check that session received the final text
        assert any(m["role"] == "user" and "availability how much rent for that" in m["content"]
                   for m in orchestrator.session.messages)


# ---------------------------------------------------------------------------
# Test G: Barge-in does not duplicate the next user turn
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_barge_in_does_not_duplicate_turn():
    """Requirement G: Barge-in cancels current TTS, clears turn state, and next turn starts cleanly."""
    pacer_mock = MagicMock()
    pacer_mock.flush = AsyncMock()
    pacer_mock.get_last_acked = MagicMock(return_value=(None, 0))
    pacer_mock.start_turn = MagicMock()
    pacer_mock.mark_turn_end = MagicMock()

    orchestrator = VoiceAgentOrchestrator(
        call_sid="test_barge_in_orch",
        stream_sid="test_stream_barge",
        pacer=pacer_mock
    )

    # Agent is speaking
    orchestrator.turn_manager.set_state(TurnState.SPEAKING)
    assert orchestrator.turn_manager.is_speaking() is True

    # User barges in
    barge_result = await orchestrator.turn_manager.trigger_barge_in()
    assert barge_result is True
    assert orchestrator.turn_manager.state == TurnState.LISTENING
    assert orchestrator.turn_manager.current_user_turn_id is None

    # Next user turn arrives
    with patch.object(orchestrator, "_stream_llm_and_tts", new_callable=AsyncMock) as mock_llm:
        committed = await orchestrator.handle_final_transcript("What about dinner?")
        assert committed is True
        await asyncio.sleep(0.05)
        assert mock_llm.call_count == 1


# ---------------------------------------------------------------------------
# Test H: Browser voice continues to work and adheres to turn contract
# ---------------------------------------------------------------------------
def test_browser_voice_websocket_turn_contract():
    """Requirement H: Browser voice WebSocket correctly handles interim and final turn events."""
    client = TestClient(app)
    with client.websocket_connect("/ws/browser-voice") as ws:
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "connected"

        # Start session
        ws.send_text(json.dumps({"event": "start", "session_id": "test_ws_turn_h"}))
        state_raw = ws.receive_text()
        state = json.loads(state_raw)
        assert state.get("event") == "session_state"

        # Send interim transcript
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "Do you have any ocean",
            "is_final": False,
            "turn_id": "ws_turn_1"
        }))

        # Send duplicate of final transcript twice
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "Do you have any ocean views?",
            "is_final": True,
            "turn_id": "ws_turn_1"
        }))

        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "Do you have any ocean views?",
            "is_final": True,
            "turn_id": "ws_turn_1"
        }))

        # Stop cleanly
        ws.send_text(json.dumps({"event": "stop"}))


# ---------------------------------------------------------------------------
# Test I: Conversation reset still works
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_conversation_reset_still_works():
    """Requirement I: Conversation reset clears turn manager history, broadcaster, and allows fresh start."""
    tm = TurnManager(session_id="test_reset")
    tm.set_state(TurnState.LISTENING)
    broadcaster = EventBroadcaster()

    # Commit turn
    tid = tm.start_user_turn()
    committed = await tm.handle_user_speech_final("Hello resort", turn_id=tid)
    assert committed is True
    await broadcaster.notify_user_transcript("Hello resort", is_final=True, turn_id=tid)
    assert len(broadcaster.state["conversation"]) == 1

    # Reset
    tm.reset()
    await broadcaster.clear_conversation()

    assert len(broadcaster.state["conversation"]) == 0
    assert len(tm.committed_turn_ids) == 0
    assert tm.last_committed_transcript is None
    assert tm.current_user_turn_id is None

    # Next turn starts fresh
    tm.set_state(TurnState.LISTENING)
    fresh_tid = tm.start_user_turn()
    assert fresh_tid == "turn_user_1"
    committed = await tm.handle_user_speech_final("Hello resort", turn_id=fresh_tid)
    assert committed is True


# ---------------------------------------------------------------------------
# Test J: Screen recording near-duplicate / refinement scenario
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_screen_recording_near_duplicate_refinement():
    """Requirement: The exact screen recording case:

    1. 'availability or not and dining sepa and how much rent for that'
    2. 'availability how much rent for that'
    Must be recognized as the SAME turn rather than two turns.
    """
    tm = TurnManager(session_id="test_screen_rec")
    tm.set_state(TurnState.LISTENING)
    broadcaster = EventBroadcaster()

    # Partials arrive during turn
    tid1 = tm.start_user_turn()
    tm.handle_user_speech_partial("availability or not", turn_id=tid1)
    await broadcaster.notify_user_transcript("availability or not", is_final=False, turn_id=tid1)

    # First version of speech turn finishes
    text1 = "availability or not and dining sepa and how much rent for that"
    committed1 = await tm.handle_user_speech_final(text1, turn_id=tid1)
    assert committed1 is True
    await broadcaster.notify_user_transcript(text1, is_final=True, turn_id=tid1)

    assert len(broadcaster.state["conversation"]) == 1
    assert broadcaster.state["conversation"][0]["content"] == text1

    # Second refined version arrives rapidly (<4s)
    text2 = "availability how much rent for that"
    tid2 = tm.start_user_turn()
    committed2 = await tm.handle_user_speech_final(text2, turn_id=tid2)

    # TurnManager must recognize this as an overlapping near-duplicate of the active turn
    assert committed2 is False, "Refined near-duplicate should NOT trigger a second agent processing turn"

    # When broadcaster receives the refined transcript, it updates the existing message in-place
    await broadcaster.notify_user_transcript(text2, is_final=True, turn_id=tid2)

    # Exactly ONE permanent user message in conversation, updated with refined text
    assert len(broadcaster.state["conversation"]) == 1
    assert broadcaster.state["conversation"][0]["role"] == "user"
    assert broadcaster.state["conversation"][0]["content"] == text2


# ---------------------------------------------------------------------------
# Test K: Refinement when assistant has already responded or started speaking
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refinement_when_assistant_message_already_interleaved():
    """Verify that even when an assistant message is appended before the refinement arrives,

    broadcaster updates the previous user message in place and does NOT create a duplicate user message.
    """
    broadcaster = EventBroadcaster()

    # User message 1 committed
    text1 = "availability or not and dining sepa and how much rent for that"
    tid1 = "turn_user_1"
    await broadcaster.notify_user_transcript(text1, is_final=True, turn_id=tid1)

    assert len(broadcaster.state["conversation"]) == 1
    assert broadcaster.state["conversation"][0]["content"] == text1

    # Assistant response arrives immediately
    asst_text = "Checking availability for suites and dining options..."
    await broadcaster.notify_agent_response(asst_text, mark_id="m1", is_final=True, turn_id=tid1)

    assert len(broadcaster.state["conversation"]) == 2
    assert broadcaster.state["conversation"][1]["role"] == "assistant"

    # Refined user speech arrives (<5s)
    text2 = "availability how much rent for that"
    tid2 = "turn_user_2"
    await broadcaster.notify_user_transcript(text2, is_final=True, turn_id=tid2)

    # Conversation must STILL have only 1 user message (updated in place) + 1 assistant message
    user_messages = [m for m in broadcaster.state["conversation"] if m.get("role") == "user"]
    assert len(user_messages) == 1, "Must NOT append duplicate user message when assistant message is interleaved"
    assert user_messages[0]["content"] == text2, "User message content must be updated to refined transcript"


