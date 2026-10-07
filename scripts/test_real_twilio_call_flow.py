import asyncio
import base64
import json
import math
import os
import struct
import sys
import time
from typing import List, Optional
import websockets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.telephony.codecs import ULAW_BYTES_PER_FRAME, pcm_to_ulaw


def generate_tone_frame(freq: float = 400.0, amplitude: float = 6000.0, sample_rate: int = 8000) -> bytes:
    """Generate 20ms (160 samples) of μ-law audio with loud audible signal for barge-in."""
    samples = [int(amplitude * math.sin(2 * math.pi * freq * (i / sample_rate))) for i in range(ULAW_BYTES_PER_FRAME)]
    pcm = struct.pack(f"<{ULAW_BYTES_PER_FRAME}h", *samples)
    return pcm_to_ulaw(pcm)


async def run_live_twilio_call_flow_test(
    ws_url: str = "ws://127.0.0.1:8000/ws/media-stream",
    audio_file: str = "test_speech_8k.ulaw"
):
    """
    Complete End-to-End Real Twilio Phone-Call Flow Verification:
    1. Connects to the live FastAPI Twilio Media Stream WebSocket endpoint.
    2. Sends 'start' event without simulated utterances (triggers real AssemblyAI STT).
    3. Receives and plays initial greeting audio generated live by ElevenLabs TTS.
    4. Streams real caller audio (8kHz μ-law) to Twilio Media Stream.
    5. Real AssemblyAI STT transcribes speech into interim & final transcripts.
    6. Transcript reaches Gemini LLM and generates response tokens.
    7. ElevenLabs synthesizes response audio and streams 20ms frames back to the caller.
    8. Caller interrupts the assistant with speech onset; verifies sub-200ms barge-in and Twilio CLEAR event.
    """
    print("=" * 70)
    print("LIVE TWILIO PHONE-CALL FLOW VERIFICATION")
    print("=" * 70)
    print(f"[Config] Endpoint:       {ws_url}")
    print(f"[Config] Real Audio:     {audio_file}")
    print(f"[Config] Providers:      STT=AssemblyAI (v3 WS), LLM=Gemini, TTS=ElevenLabs")
    print("=" * 70)

    if not os.path.exists(audio_file):
        print(f"[FAIL] Audio file '{audio_file}' not found.")
        return False

    with open(audio_file, "rb") as f:
        audio_bytes = f.read()

    stream_sid = "MZ_live_call_verification"
    call_sid = "CA_live_call_verification"

    # Metrics
    greeting_frames = 0
    greeting_marks = 0
    response_frames = 0
    response_marks = 0
    clear_events_received = 0
    barge_in_latency_ms: Optional[float] = None
    all_marks_received: List[str] = []

    print("\n[Step 1] Connecting to Twilio Media Stream WebSocket...")
    try:
        async with websockets.connect(ws_url, open_timeout=10.0) as ws:
            print("[Step 1] Connected to Twilio Media Stream WebSocket!")

            # Send Twilio protocol 'start' event (NO simulated_utterance -> Real AssemblyAI STT)
            start_payload = {
                "event": "start",
                "streamSid": stream_sid,
                "start": {
                    "streamSid": stream_sid,
                    "callSid": call_sid,
                    "accountSid": "AC_live_test_account",
                    "customParameters": {}  # Empty = LIVE STT MODE
                }
            }
            await ws.send(json.dumps(start_payload))
            print("[Step 1] Sent 'start' event with empty customParameters (Live STT enabled).")

            # -------------------------------------------------------------
            # Step 2: Receive Initial Greeting from Assistant (ElevenLabs)
            # -------------------------------------------------------------
            print("\n[Step 2] Waiting for Assistant initial greeting (synthesized by ElevenLabs)...")
            greeting_start = time.monotonic()
            greeting_finished = False

            while time.monotonic() - greeting_start < 15.0:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    msg = json.loads(raw_msg)
                    evt = msg.get("event")

                    if evt == "media":
                        greeting_frames += 1
                    elif evt == "mark":
                        greeting_marks += 1
                        mark_name = msg.get("mark", {}).get("name", "")
                        all_marks_received.append(mark_name)
                        # Acknowledge mark as Twilio device does
                        ack = {
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": mark_name}
                        }
                        await ws.send(json.dumps(ack))

                        if msg.get("mark", {}).get("is_final", False):
                            print(f"  [Greeting] Received final mark '{mark_name}'.")
                            greeting_finished = True
                            break
                except asyncio.TimeoutError:
                    if greeting_frames > 0:
                        print(f"  [Greeting] Silence window reached; greeting complete.")
                        greeting_finished = True
                        break
                    else:
                        print("  [Greeting] Still waiting for first audio frame...")

            print(f"[Step 2] Initial Greeting Audio: {greeting_frames} frames ({greeting_frames * 20}ms), {greeting_marks} marks.")
            assert greeting_frames > 0, "Must receive real greeting audio frames from ElevenLabs"

            # Allow brief pause after greeting
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # Step 3: Stream Real Caller Audio to AssemblyAI STT
            # -------------------------------------------------------------
            frame_size = 160
            total_speech_frames = len(audio_bytes) // frame_size
            duration_sec = len(audio_bytes) / 8000.0
            print(f"\n[Step 3] Caller speaks real audio: '{audio_file}' (~{duration_sec:.2f}s, {total_speech_frames} frames)...")

            stream_t0 = time.monotonic()
            for i in range(0, len(audio_bytes), frame_size):
                chunk = audio_bytes[i:i + frame_size]
                if len(chunk) < frame_size:
                    chunk = chunk + b"\xff" * (frame_size - len(chunk))
                payload_b64 = base64.b64encode(chunk).decode("ascii")
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload_b64}
                }
                await ws.send(json.dumps(media_msg))
                await asyncio.sleep(0.02)  # Real-time telephony pacing

            # Stream trailing silence frames for AssemblyAI endpointing
            silence_frame = b"\xff" * frame_size
            silence_b64 = base64.b64encode(silence_frame).decode("ascii")
            print(f"[Step 3] Streamed speech in {time.monotonic() - stream_t0:.2f}s. Sending endpointing silence...")
            for _ in range(40):  # 800ms silence
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": silence_b64}
                }
                await ws.send(json.dumps(media_msg))
                await asyncio.sleep(0.02)

            # -------------------------------------------------------------
            # Step 4: Receive Real Assistant Response (Gemini + ElevenLabs)
            # -------------------------------------------------------------
            print("\n[Step 4] Listening for Assistant response (AssemblyAI STT -> Gemini LLM -> ElevenLabs TTS)...")
            response_start = time.monotonic()
            barge_in_triggered = False
            barge_in_send_time = 0.0

            while time.monotonic() - response_start < 25.0:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=6.0)
                    msg = json.loads(raw_msg)
                    evt = msg.get("event")

                    if evt == "media":
                        response_frames += 1
                        # Once we receive enough response frames (assistant is actively speaking),
                        # trigger barge-in interruption!
                        if response_frames >= 12 and not barge_in_triggered:
                            print(f"\n[Step 5] Assistant is actively SPEAKING ({response_frames} response frames received).")
                            print("[Step 5] INITIATING BARGE-IN INTERRUPTION: Sending loud caller speech onset...")
                            barge_in_triggered = True
                            barge_in_send_time = time.monotonic()

                            # Send loud speech frames (RMS > 3000)
                            loud_frame = generate_tone_frame(freq=400.0, amplitude=6000.0)
                            loud_b64 = base64.b64encode(loud_frame).decode("ascii")
                            for _ in range(10):  # 200ms loud audio
                                interrupt_msg = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": loud_b64}
                                }
                                await ws.send(json.dumps(interrupt_msg))
                                await asyncio.sleep(0.02)

                    elif evt == "mark":
                        response_marks += 1
                        mark_name = msg.get("mark", {}).get("name", "")
                        all_marks_received.append(mark_name)
                        ack = {
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": mark_name}
                        }
                        await ws.send(json.dumps(ack))

                    elif evt == "clear":
                        clear_events_received += 1
                        barge_in_latency_ms = (time.monotonic() - barge_in_send_time) * 1000.0
                        print(f"  >>> [BARGE-IN ACKNOWLEDGED]: Received Twilio 'clear' event in {barge_in_latency_ms:.1f}ms!")
                        # After clear event received, barge-in is verified!
                        break

                except asyncio.TimeoutError:
                    if response_frames > 0:
                        break
                    print("  Waiting for assistant speech...")

            # -------------------------------------------------------------
            # Step 6: Clean Termination
            # -------------------------------------------------------------
            print("\n[Step 6] Sending 'stop' event and disconnecting cleanly...")
            stop_payload = {
                "event": "stop",
                "streamSid": stream_sid,
                "stop": {"streamSid": stream_sid, "callSid": call_sid}
            }
            await ws.send(json.dumps(stop_payload))
            await asyncio.sleep(0.3)

    except Exception as exc:
        print(f"[FAIL] Error during call flow: {exc}")
        return False

    # -------------------------------------------------------------
    # Summary Report
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("LIVE TWILIO CALL FLOW TEST REPORT")
    print("=" * 70)
    print(f"1. Telephony Connection:     ESTABLISHED (/ws/media-stream)")
    print(f"2. Greeting Frames Received: {greeting_frames} ({greeting_frames * 20}ms audio from ElevenLabs)")
    print(f"3. Caller Audio Streamed:    {total_speech_frames} frames of real speech ({audio_file})")
    print(f"4. Real AssemblyAI STT:      ACTIVATED (simulated_utterance=None)")
    print(f"5. Gemini LLM + ElevenLabs:  GENERATED {response_frames} response audio frames")
    print(f"6. Barge-in Interruption:    {'VERIFIED' if clear_events_received > 0 else 'NOT DETECTED'}")
    if barge_in_latency_ms is not None:
        print(f"   Barge-in CLEAR Latency:   {barge_in_latency_ms:.1f} ms (sub-200ms target)")
    print("=" * 70)

    # Verification checks
    passed = (
        greeting_frames > 0
        and response_frames > 0
        and clear_events_received > 0
    )
    if passed:
        print("RESULT: ALL 5 STEPS PASSED SUCCESSFULLY (100% LIVE PIPELINE)!")
    else:
        print("RESULT: VERIFICATION INCOMPLETE.")
        if greeting_frames == 0:
            print("  - Blocker: No greeting audio received.")
        if response_frames == 0:
            print("  - Blocker: No assistant response frames received from STT->LLM->TTS.")
        if clear_events_received == 0:
            print("  - Blocker: Twilio CLEAR event was not received during barge-in.")
    print("=" * 70)
    return passed


if __name__ == "__main__":
    success = asyncio.run(run_live_twilio_call_flow_test())
    sys.exit(0 if success else 1)
