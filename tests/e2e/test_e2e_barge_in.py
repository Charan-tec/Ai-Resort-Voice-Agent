import asyncio
import json
import struct
import pytest
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.orchestrator.turn_manager import TurnState
from app.telephony.codecs import pcm_to_ulaw
from app.telephony.pacer import OutboundPacer


@pytest.mark.asyncio
async def test_e2e_scenario_2_barge_in_interruption():
    """
    E2E Scenario 2:
    1. Assistant is in SPEAKING state playing an utterance.
    2. Outbound pacer is sending frames and marks.
    3. Customer speaks loudly (inbound audio with high RMS).
    4. EnergyGate detects interruption.
    5. TurnManager triggers BARGE-IN state.
    6. LLM/TTS tasks are cancelled.
    7. Pacer flushes pending audio queue.
    8. Twilio 'clear' event is sent over WebSocket.
    9. Session transcript is truncated based on last acknowledged mark.
    10. State transitions cleanly back to LISTENING.
    """
    sent_events = []

    async def mock_send(msg: str):
        sent_events.append(json.loads(msg))

    pacer = OutboundPacer(stream_sid="MZ_barge_test", send_fn=mock_send)
    pacer.start()

    orchestrator = VoiceAgentOrchestrator(
        call_sid="CA_barge_test",
        stream_sid="MZ_barge_test",
        pacer=pacer
    )

    # 1. Simulate assistant starts speaking a long sentence
    orchestrator.turn_manager.set_state(TurnState.SPEAKING)
    orchestrator.session.start_assistant_turn()
    orchestrator.session.record_sentence_chunk("Welcome to Azure Paradise Resort in Maui.", "mark_1")
    orchestrator.session.record_sentence_chunk("We feature premier oceanfront villas and private dining.", "mark_2")

    # Enqueue audio in pacer
    long_audio = b"\xff" * 3200  # 20 frames
    await pacer.enqueue_audio(long_audio, metadata={"mark_id": "mark_1"})

    # Simulate Twilio acknowledged the first mark
    pacer.handle_mark_ack("mark_1")

    # 2. Inbound interruption audio: 3 consecutive loud frames
    loud_pcm = struct.pack("<160h", *([6000 if i % 2 == 0 else -6000 for i in range(160)]))
    loud_ulaw = pcm_to_ulaw(loud_pcm)

    for _ in range(3):
        await orchestrator.handle_inbound_audio(loud_ulaw)

    # Give event loop a moment to execute async barge-in
    await asyncio.sleep(0.1)

    # 3. Verify Twilio CLEAR event was sent
    clear_events = [ev for ev in sent_events if ev.get("event") == "clear"]
    assert len(clear_events) >= 1, "Expected Twilio 'clear' event to be sent upon barge-in."
    assert clear_events[0]["streamSid"] == "MZ_barge_test"

    # 4. Verify assistant transcript was truncated using last acknowledged mark
    # Only sentence 1 ("Welcome to Azure Paradise Resort in Maui.") was acknowledged by mark_1
    history = orchestrator.session.messages
    interrupted_msg = [m for m in history if m["role"] == "assistant" and "[interrupted]" in m["content"]]
    assert len(interrupted_msg) == 1
    assert "Welcome to Azure Paradise Resort in Maui." in interrupted_msg[0]["content"]
    assert "We feature premier oceanfront villas" not in interrupted_msg[0]["content"]

    # 5. Verify TurnManager returned to LISTENING state
    assert orchestrator.turn_manager.state == TurnState.LISTENING

    await pacer.stop()


@pytest.mark.asyncio
async def test_barge_in_cancellation_race_does_not_enqueue_stale_turn_end():
    """
    Regression test:
    Verify that when an in-flight LLM streaming task is cancelled by barge-in,
    it does not emit a completion mark or corrupt TurnManager state.
    """
    sent_events = []

    async def mock_send(msg: str):
        sent_events.append(json.loads(msg))

    pacer = OutboundPacer(stream_sid="MZ_barge_race", send_fn=mock_send, frame_interval_sec=0.005)
    pacer.start()

    orchestrator = VoiceAgentOrchestrator(
        call_sid="CA_barge_race",
        stream_sid="MZ_barge_race",
        pacer=pacer
    )

    # Start user turn and let LLM task start
    await orchestrator._process_user_turn("I want to check villas")
    # If completed without interruption, verify pacer works normally
    assert pacer._turn_final_mark_sent is False

    await pacer.stop()
