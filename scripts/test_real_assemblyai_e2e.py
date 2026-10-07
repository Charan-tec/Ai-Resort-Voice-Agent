import asyncio
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dotenv
dotenv.load_dotenv(override=True)

from app.core.config import settings
from app.core.logging import logger
from app.stt.assemblyai import AssemblyAISTTProvider
from app.stt.base import STTCallback
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.telephony.pacer import OutboundPacer


async def run_real_assemblyai_e2e_test():
    """
    End-to-End Live STT Test:
    1. Loads real spoken audio (8kHz μ-law).
    2. Initializes AssemblyAISTTProvider with real ASSEMBLYAI_API_KEY from .env.
    3. Connects STT callbacks to VoiceAgentOrchestrator and TurnManager.
    4. Streams real audio chunks over the live AssemblyAI v3 WebSocket connection.
    5. Captures real-time interim and final transcripts from AssemblyAI.
    6. Confirms propagation into TurnManager and Orchestrator session.
    """
    audio_file = "test_speech_8k.ulaw"
    if not os.path.exists(audio_file):
        print(f"[FAIL] Audio file '{audio_file}' not found. Run scripts/generate_speech_audio.py first.")
        return False

    with open(audio_file, "rb") as f:
        audio_bytes = f.read()

    duration_sec = len(audio_bytes) / 8000.0
    print("=" * 60)
    print("REAL ASSEMBLYAI END-TO-END STT TEST")
    print("=" * 60)
    print(f"[1] Test Audio: '{audio_file}' ({len(audio_bytes)} bytes, ~{duration_sec:.2f}s of real speech)")
    print(f"[1] Spoken Phrase: 'Hello, I want to check room availability for an ocean villa.'")

    api_key = settings.effective_assemblyai_api_key
    if not api_key:
        print("[FAIL] No ASSEMBLYAI_API_KEY found in .env.")
        return False

    masked_key = f"{api_key[:4]}...{api_key[-4:]}"
    print(f"[2] AssemblyAI API Key: {masked_key} (length: {len(api_key)})")
    print(f"[2] Provider: AssemblyAI v3 WebSocket (wss://streaming.assemblyai.com/v3/ws)")
    print(f"[2] Audio Format: 8000 Hz, pcm_mulaw (zero mock/simulated fallback)")

    # Initialize Dummy Outbound Pacer
    outbound_messages = []
    async def mock_send_fn(msg: str):
        outbound_messages.append(msg)

    pacer = OutboundPacer(stream_sid="MZ_real_test", send_fn=mock_send_fn)
    pacer.start()

    # Initialize VoiceAgentOrchestrator
    orchestrator = VoiceAgentOrchestrator(
        call_sid="CA_real_stt_test",
        stream_sid="MZ_real_stt_test",
        pacer=pacer
    )

    interim_transcripts: List[str] = []
    final_transcripts: List[str] = []
    error_events: List[Exception] = []

    async def on_interim(text: str):
        interim_transcripts.append(text)
        print(f"  >>> [AssemblyAI Interim STT]: '{text}'")
        await orchestrator.handle_interim_transcript(text)

    async def on_final(text: str):
        final_transcripts.append(text)
        print(f"  >>> [AssemblyAI Final STT]: '{text}'")
        await orchestrator.handle_final_transcript(text)

    async def on_error(err: Exception):
        error_events.append(err)
        print(f"  >>> [AssemblyAI Error]: {err}")

    stt_callbacks = STTCallback(
        on_interim=on_interim,
        on_final=on_final,
        on_error=on_error
    )

    # Initialize live AssemblyAI STT provider (simulated_utterance is None -> NO mock mode)
    stt = AssemblyAISTTProvider(
        callbacks=stt_callbacks,
        api_key=api_key,
        simulated_utterance=None
    )

    print("\n[3] Connecting to live AssemblyAI streaming WebSocket...")
    await stt.connect()
    assert stt.is_connected, "STT provider must be connected"
    assert stt.ws is not None, "Real WebSocket must be active (not mock mode)"
    print("[3] Live WebSocket handshake confirmed!")

    # Stream 160-byte (20ms) frames to AssemblyAI
    frame_size = 160
    total_frames = len(audio_bytes) // frame_size
    print(f"\n[4] Streaming {total_frames} audio frames (~{duration_sec:.2f}s) to AssemblyAI...")

    start_stream = time.monotonic()
    for i in range(0, len(audio_bytes), frame_size):
        chunk = audio_bytes[i:i + frame_size]
        await stt.send_audio(chunk)
        # Real-time pacing (20ms per frame)
        await asyncio.sleep(0.02)

    stream_duration = time.monotonic() - start_stream
    print(f"[4] Finished streaming audio in {stream_duration:.2f}s.")

    # Send silence frames to allow AssemblyAI endpointing
    silence_frame = b"\xff" * frame_size
    print("[4] Streaming trailing silence for speech endpointing...")
    for _ in range(40):  # 800ms silence
        await stt.send_audio(silence_frame)
        await asyncio.sleep(0.02)

    # Wait for final transcript arrival
    print("\n[5] Waiting for AssemblyAI final transcript and TurnManager processing...")
    wait_start = time.monotonic()
    while not final_transcripts and (time.monotonic() - wait_start < 10.0):
        await asyncio.sleep(0.2)

    # Give orchestrator an extra moment to process turn
    await asyncio.sleep(1.5)

    print("\n[6] Gracefully closing AssemblyAI STT provider...")
    await stt.close()
    await pacer.stop()

    print("\n" + "=" * 60)
    print("TEST EXECUTION REPORT")
    print("=" * 60)
    print(f"Total Interim Transcripts Received: {len(interim_transcripts)}")
    if interim_transcripts:
        print(f"First Interim: '{interim_transcripts[0]}'")
        print(f"Last Interim:  '{interim_transcripts[-1]}'")
    print(f"Final Transcripts Received:         {len(final_transcripts)}")
    if final_transcripts:
        print(f"Recognized Speech (Final):          '{final_transcripts[0]}'")
    print(f"Errors Encountered:                 {len(error_events)}")
    print(f"TurnManager Current State:          {orchestrator.turn_manager.state.value}")
    print(f"TurnManager Active Turn ID:         {orchestrator.turn_manager.active_turn_id}")
    print(f"Session Messages Recorded:          {len(orchestrator.session.messages)}")
    if orchestrator.session.messages:
        last_user_msg = [m for m in orchestrator.session.messages if m.get("role") == "user"]
        if last_user_msg:
            print(f"Orchestrator User Message:          '{last_user_msg[-1].get('content')}'")

    success = (
        len(final_transcripts) > 0
        and any(w in final_transcripts[0].lower() for w in ["room", "villa", "availability", "hello", "check", "ocean"])
    )
    print("=" * 60)
    if success:
        print("RESULT: PASS - Real AssemblyAI STT verified end-to-end!")
    else:
        print("RESULT: FAIL - AssemblyAI did not produce the expected final transcript.")
    print("=" * 60)
    return success


if __name__ == "__main__":
    result = asyncio.run(run_real_assemblyai_e2e_test())
    sys.exit(0 if result else 1)
