import asyncio
import base64
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.telephony.codecs import ULAW_BYTES_PER_FRAME
from scripts.simulate_call import generate_tone_frame


def test_websocket_media_stream_dialogue():
    """
    Integration test verifying the full Twilio Media Stream WebSocket flow:
    1. Connects to /ws/media-stream.
    2. Sends 'start' event with simulated customParameters.
    3. Receives assistant initial greeting media frames and mark events.
    4. Acknowledges all greeting marks and drains all greeting audio until is_last=True.
    5. Sends simulated speech audio frames with energy + silence endpointing.
    6. Receives assistant response media frames and marks, starting strictly after caller speech.
    7. Sends 'stop' event and cleanly disconnects.
    """
    client = TestClient(app)
    with client.websocket_connect("/ws/media-stream") as ws:
        stream_sid = "MZ_pytest_stream_001"
        call_sid = "CA_pytest_call_001"

        # 1. Send start event
        start_payload = {
            "event": "start",
            "streamSid": stream_sid,
            "start": {
                "streamSid": stream_sid,
                "callSid": call_sid,
                "accountSid": "AC_pytest_account",
                "customParameters": {
                    "simulated_utterance": "I want to check room availability for next weekend."
                }
            }
        }
        ws.send_text(json.dumps(start_payload))

        # 2. Receive assistant initial greeting - drain all frames until final mark
        greeting_media_count = 0
        greeting_mark_count = 0

        for _ in range(50):
            raw = ws.receive_text()
            data = json.loads(raw)
            event = data.get("event")
            if event == "media":
                greeting_media_count += 1
            elif event == "mark":
                greeting_mark_count += 1
                mark_obj = data.get("mark", {})
                mark_name = mark_obj.get("name")
                is_last = mark_obj.get("is_last", False)
                is_final = mark_obj.get("is_final", False)
                ack = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": mark_name}
                }
                ws.send_text(json.dumps(ack))
                if is_final:
                    break

        assert greeting_media_count == 20, f"Expected 20 greeting audio frames, got {greeting_media_count}"
        assert greeting_mark_count == 2, f"Expected 2 greeting marks (periodic + final), got {greeting_mark_count}"

        # 3. Caller speaks: send 30 frames of audible tone
        tone_frame = generate_tone_frame(freq=400.0, amplitude=4500.0)
        payload_b64 = base64.b64encode(tone_frame).decode("ascii")
        for _ in range(30):
            media_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload_b64}
            }
            ws.send_text(json.dumps(media_msg))

        # Followed by 20 frames of silence for STT endpointing
        silence_b64 = base64.b64encode(b"\xff" * ULAW_BYTES_PER_FRAME).decode("ascii")
        for _ in range(20):
            silence_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": silence_b64}
            }
            ws.send_text(json.dumps(silence_msg))

        # 4. Receive assistant response - verified that response marks start after greeting
        response_media_count = 0
        response_marks = []
        final_mark_received = False

        for _ in range(100):
            raw = ws.receive_text()
            data = json.loads(raw)
            event = data.get("event")
            if event == "media":
                response_media_count += 1
            elif event == "mark":
                mark_obj = data.get("mark", {})
                mark_name = mark_obj.get("name")
                is_last = mark_obj.get("is_last", False)
                is_final = mark_obj.get("is_final", False)
                response_marks.append({
                    "name": mark_name,
                    "is_last": is_last,
                    "is_final": is_final
                })
                ack = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": mark_name}
                }
                ws.send_text(json.dumps(ack))
                if is_final:
                    final_mark_received = True
                    break

        assert response_media_count > 0, "Expected assistant response audio frames"
        assert len(response_marks) >= 1, "Expected assistant response mark"
        assert response_marks[0]["name"] == "mark_3", f"Expected response to start at mark_3, got {response_marks[0]['name']}"
        assert final_mark_received is True, "Expected to receive final mark with is_final=True"
        assert response_marks[-1]["is_final"] is True, "Last mark must have is_final=True"

        # 5. Send stop event
        stop_payload = {
            "event": "stop",
            "streamSid": stream_sid,
            "stop": {"callSid": call_sid}
        }
        ws.send_text(json.dumps(stop_payload))


def test_multi_mark_greeting_drain_and_accounting_isolation():
    """
    Validates:
    1. Multiple greeting marks (periodic mark_1 at 15 frames, final mark_2 at 20 frames)
       are acknowledged without premature loop exit.
    2. All 20 greeting frames are fully drained before caller speech begins.
    3. Greeting frames are strictly accounted as greeting frames (not response frames).
    4. Outbound pacer communicates is_last and is_final correctly on completion marks.
    5. Disconnects cleanly without deadlock or hanging.
    """
    client = TestClient(app)
    with client.websocket_connect("/ws/media-stream") as ws:
        stream_sid = "MZ_pytest_drain_002"
        call_sid = "CA_pytest_drain_002"

        start_payload = {
            "event": "start",
            "streamSid": stream_sid,
            "start": {
                "streamSid": stream_sid,
                "callSid": call_sid,
                "accountSid": "AC_pytest_account",
                "customParameters": {
                    "simulated_utterance": "Do you have villas available?"
                }
            }
        }
        ws.send_text(json.dumps(start_payload))

        greeting_frames = 0
        received_marks = []

        # Drain greeting until final mark
        for _ in range(50):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("event") == "media":
                greeting_frames += 1
            elif data.get("event") == "mark":
                mark_obj = data.get("mark", {})
                mark_name = mark_obj.get("name")
                is_last = mark_obj.get("is_last", False)
                is_final = mark_obj.get("is_final", False)
                received_marks.append({
                    "name": mark_name,
                    "frame_at": greeting_frames,
                    "is_last": is_last,
                    "is_final": is_final
                })
                # Send mark ACK back to server
                ws.send_text(json.dumps({
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": mark_name}
                }))
                if is_final:
                    break

        # Verification 1: Exactly 2 marks received (mark_1 periodic at 15 frames, mark_2 final at 20 frames)
        assert len(received_marks) == 2, f"Expected 2 greeting marks, got {len(received_marks)}"
        assert received_marks[0]["name"] == "mark_1"
        assert received_marks[0]["frame_at"] == 15
        assert received_marks[0]["is_last"] is False
        assert received_marks[0]["is_final"] is False

        assert received_marks[1]["name"] == "mark_2"
        assert received_marks[1]["frame_at"] == 20
        assert received_marks[1]["is_last"] is True
        assert received_marks[1]["is_final"] is True

        # Verification 2: Exactly 20 greeting frames accounted before any caller speech
        assert greeting_frames == 20

        # Send stop event and verify clean termination
        ws.send_text(json.dumps({
            "event": "stop",
            "streamSid": stream_sid,
            "stop": {"callSid": call_sid}
        }))


def test_multi_chunk_response_intermediate_marks_do_not_exit():
    """
    Integration test verifying that during an assistant response turn:
    1. Greeting is fully drained.
    2. Caller utterance is sent.
    3. Any intermediate response marks have is_final=False.
    4. Client does NOT terminate prematurely on intermediate marks.
    5. The final mark of the turn has is_final=True.
    6. Completes cleanly without hanging.
    """
    client = TestClient(app)
    with client.websocket_connect("/ws/media-stream") as ws:
        stream_sid = "MZ_pytest_stream_multi"
        call_sid = "CA_pytest_call_multi"

        start_payload = {
            "event": "start",
            "streamSid": stream_sid,
            "start": {
                "streamSid": stream_sid,
                "callSid": call_sid,
                "accountSid": "AC_pytest_account",
                "customParameters": {
                    "simulated_utterance": "I want to check room availability for next weekend."
                }
            }
        }
        ws.send_text(json.dumps(start_payload))

        # Drain greeting
        for _ in range(50):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("event") == "mark":
                mark_obj = data.get("mark", {})
                mark_name = mark_obj.get("name")
                is_final = mark_obj.get("is_final", False)
                ws.send_text(json.dumps({
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": mark_name}
                }))
                if is_final:
                    break

        # Caller speaks
        tone_frame = generate_tone_frame(freq=400.0, amplitude=4500.0)
        payload_b64 = base64.b64encode(tone_frame).decode("ascii")
        for _ in range(30):
            ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload_b64}
            }))

        silence_b64 = base64.b64encode(b"\xff" * ULAW_BYTES_PER_FRAME).decode("ascii")
        for _ in range(20):
            ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": silence_b64}
            }))

        # Listen for response marks
        response_marks = []
        for _ in range(100):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("event") == "mark":
                mark_obj = data.get("mark", {})
                mark_name = mark_obj.get("name")
                is_last = mark_obj.get("is_last", False)
                is_final = mark_obj.get("is_final", False)
                response_marks.append({
                    "name": mark_name,
                    "is_last": is_last,
                    "is_final": is_final
                })
                ws.send_text(json.dumps({
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": mark_name}
                }))
                if is_final:
                    break

        assert len(response_marks) >= 1, "Expected at least one response mark"
        # All marks except the last must have is_final=False
        for intermediate_mark in response_marks[:-1]:
            assert intermediate_mark["is_final"] is False, (
                f"Intermediate mark {intermediate_mark['name']} must have is_final=False!"
            )
        # The last mark must have is_final=True
        assert response_marks[-1]["is_final"] is True, "The final mark must have is_final=True!"

        ws.send_text(json.dumps({
            "event": "stop",
            "streamSid": stream_sid,
            "stop": {"callSid": call_sid}
        }))
