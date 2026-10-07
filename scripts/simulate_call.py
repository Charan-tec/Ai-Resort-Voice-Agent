import asyncio
import base64
import json
import math
import os
import struct
import sys
import time
import websockets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.telephony.codecs import ULAW_BYTES_PER_FRAME, pcm_to_ulaw


def generate_tone_frame(freq: float = 400.0, amplitude: float = 4000.0, sample_rate: int = 8000) -> bytes:
    """Generate 20ms (160 samples) of μ-law audio containing an audible signal."""
    samples = [int(amplitude * math.sin(2 * math.pi * freq * (i / sample_rate))) for i in range(ULAW_BYTES_PER_FRAME)]
    pcm = struct.pack(f"<{ULAW_BYTES_PER_FRAME}h", *samples)
    return pcm_to_ulaw(pcm)


async def run_call_simulation(
    ws_url: str = "ws://127.0.0.1:8000/ws/media-stream",
    user_prompt: str = "I want to check room availability for next weekend."
):
    """
    Interactive call simulator:
    1. Connects to Twilio Media Stream WebSocket.
    2. Sends 'start' event with simulated CallSid, StreamSid, and customParameters.
    3. Receives and acknowledges the assistant's initial welcome greeting.
    4. Streams simulated user speech audio frames (with audible signal) + silence endpointing.
    5. Listens for outbound media and mark events representing assistant response.
    6. Sends 'stop' event and cleanly disconnects.
    """
    print(f"Connecting to {ws_url}...")
    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected to Twilio Media Stream WebSocket!")
            stream_sid = "MZ_sim_stream_001"
            call_sid = "CA_sim_call_001"

            # 1. Send start event
            start_payload = {
                "event": "start",
                "streamSid": stream_sid,
                "start": {
                    "streamSid": stream_sid,
                    "callSid": call_sid,
                    "accountSid": "AC_sim_account",
                    "customParameters": {
                        "simulated_utterance": user_prompt
                    }
                }
            }
            await ws.send(json.dumps(start_payload))
            print("Sent 'start' event. Waiting for assistant initial greeting...")

            # 2. Receive assistant initial greeting (media frames and marks)
            greeting_frames = 0
            greeting_marks = 0
            last_mark_greeting_frames = 0

            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(msg)
                    event = data.get("event")
                    if event == "media":
                        greeting_frames += 1
                    elif event == "mark":
                        greeting_marks += 1
                        mark_obj = data.get("mark", {})
                        mark_name = mark_obj.get("name")
                        is_last = mark_obj.get("is_last", False)
                        is_final = mark_obj.get("is_final", False)
                        incremental = greeting_frames - last_mark_greeting_frames
                        last_mark_greeting_frames = greeting_frames
                        print(f"  [Greeting] Received mark: {mark_name} (incremental: {incremental} frames, cumulative: {greeting_frames} frames)")
                        ack = {
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": mark_name}
                        }
                        await ws.send(json.dumps(ack))
                        if is_final:
                            # Final completion mark received; greeting has completely finished playing all frames
                            break
                except asyncio.TimeoutError:
                    print(f"Greeting window closed. Total frames received: {greeting_frames}")
                    break

            print(f"Assistant greeting received! (Audio frames: {greeting_frames}, Marks: {greeting_marks})")
            await asyncio.sleep(0.3)

            # 3. Simulate caller speaking
            print(f"Caller speaking: '{user_prompt}'")
            speech_frame = generate_tone_frame(freq=400.0, amplitude=4500.0)
            # Send 40 frames (800ms) of audible speech signal
            for _ in range(40):
                payload_b64 = base64.b64encode(speech_frame).decode("ascii")
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload_b64}
                }
                await ws.send(json.dumps(media_msg))
                await asyncio.sleep(0.02)

            # Followed by 20 frames (400ms) of silence for VAD/STT endpointing
            silence_frame = b"\xff" * ULAW_BYTES_PER_FRAME
            for _ in range(20):
                payload_b64 = base64.b64encode(silence_frame).decode("ascii")
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload_b64}
                }
                await ws.send(json.dumps(media_msg))
                await asyncio.sleep(0.02)

            print("Sent caller speech frames + endpointing silence.")
            print("Listening for assistant response...")

            # 4. Listen for assistant response
            response_frames = 0
            response_marks = 0
            last_mark_response_frames = 0
            response_texts = []
            captured_tool_result = None

            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=40.0)
                    data = json.loads(msg)
                    event = data.get("event")
                    if event == "media":
                        response_frames += 1
                    elif event == "mark":
                        response_marks += 1
                        mark_obj = data.get("mark", {})
                        mark_name = mark_obj.get("name")
                        is_last = mark_obj.get("is_last", False)
                        is_final = mark_obj.get("is_final", False)
                        incremental = response_frames - last_mark_response_frames
                        last_mark_response_frames = response_frames

                        text_chunk = mark_obj.get("text")
                        if text_chunk and (not response_texts or response_texts[-1] != text_chunk):
                            response_texts.append(text_chunk)
                        if mark_obj.get("tool_result"):
                            captured_tool_result = mark_obj.get("tool_result")

                        print(f"  [Response] Acknowledging mark: {mark_name} (incremental: {incremental} frames, cumulative: {response_frames} frames)")
                        ack = {
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": mark_name}
                        }
                        await ws.send(json.dumps(ack))
                        if is_final and response_frames > 0:
                            # Assistant response turn is complete
                            break
                except asyncio.TimeoutError:
                    print(f"Assistant response completed. (Frames: {response_frames}, Marks: {response_marks})")
                    break

            # 5. Send stop event
            stop_payload = {
                "event": "stop",
                "streamSid": stream_sid,
                "stop": {"callSid": call_sid}
            }
            await ws.send(json.dumps(stop_payload))
            print("Call simulation completed cleanly.")
            final_assistant_text = " ".join(response_texts).strip()
            print("==================================================")
            print("CALL SIMULATION REPORT:")
            print(f"- Final Assistant Response: '{final_assistant_text}'")
            print(f"- Tool Result:              {captured_tool_result}")
            print(f"- Initial Greeting Audio Frames: {greeting_frames} (isolated, prior to user speech)")
            print(f"- Initial Greeting Marks:        {greeting_marks}")
            print(f"- Response Audio Frames:         {response_frames} (isolated, strictly after user speech)")
            print(f"- Response Marks Acknowledged:   {response_marks}")
            print(f"- Total Inbound Audio Frames:    {greeting_frames + response_frames}")
            print("==================================================")

    except Exception as exc:
        print(f"Simulation failed: {exc}")


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "I would like to check room availability for an ocean villa from October 1 2026 to October 5 2026 for 2 guests."
    asyncio.run(run_call_simulation(user_prompt=prompt))
