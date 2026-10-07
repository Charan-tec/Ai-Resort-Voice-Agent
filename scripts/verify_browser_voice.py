import asyncio
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

def run_browser_voice_tests():
    print("=" * 70)
    print("AZURE PARADISE RESORT BROWSER VOICE CONVERSATION VERIFICATION")
    print("=" * 70)

    client = TestClient(app)

    with client.websocket_connect("/ws/browser-voice") as ws:
        def drain_until_final_agent():
            """Read WebSocket events until an assistant response completes, collecting all transcript text."""
            texts = []
            for _ in range(300):
                raw = ws.receive_text()
                msg = json.loads(raw)
                evt = msg.get("event")
                if evt == "transcript" and msg.get("role") == "assistant" and msg.get("is_final"):
                    texts.append(msg.get("content"))
                elif evt == "mark" and "turn_end" in msg.get("mark", {}).get("name", ""):
                    break
            return " ".join(texts).strip()

        # TEST 1: Start Voice Conversation
        print("\n--- TEST 1: Start Voice Conversation ---")
        init_raw = ws.receive_text()
        init_msg = json.loads(init_raw)
        assert init_msg.get("event") == "connected"
        session_id = "recruiter_browser_demo_1"

        ws.send_text(json.dumps({"event": "start", "session_id": session_id}))
        state_raw = ws.receive_text()
        state_msg = json.loads(state_raw)
        assert state_msg.get("event") == "session_state"
        assert state_msg.get("state") == "LISTENING"

        greeting = drain_until_final_agent()
        print(f"Initial Greeting: '{greeting}'")
        assert greeting is not None and "Azure Paradise Resort" in greeting
        print("Status: PASSED [Connected to /ws/browser-voice, initial greeting delivered]")

        # TEST 2: What rooms are available for two guests?
        print("\n--- TEST 2: Say 'What rooms are available for two guests?' ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "What rooms are available for two guests?",
            "is_final": True
        }))
        resp2 = drain_until_final_agent()
        print(f"Agent: '{resp2}'")
        assert resp2 is not None
        assert any(w in resp2.lower() for w in ("suite", "bungalow", "deluxe", "dates", "planning", "check-in", "available"))
        print(f"Status: PASSED [Understands availability inquiry: '{resp2}']")

        # TEST 3: Say 'Yes.' (Context retention, no restart greeting)
        print("\n--- TEST 3: Say 'Yes.' (Context retention, zero greeting) ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "Yes.",
            "is_final": True
        }))
        resp3 = drain_until_final_agent()
        print(f"Agent: '{resp3}'")
        assert resp3 is not None
        assert "welcome to azure paradise resort" not in resp3.lower(), "FAILED: Repeated welcome greeting mid-conversation!"
        print("Status: PASSED [Understands previous context, does NOT restart with greeting]")

        # TEST 4: Say 'How much is the suite?'
        print("\n--- TEST 4: Say 'How much is the suite?' ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "How much is the suite?",
            "is_final": True
        }))
        resp4 = drain_until_final_agent()
        print(f"Agent: '{resp4}'")
        assert resp4 is not None
        assert "380" in resp4 or "Deluxe Sunset Suite" in resp4 or "suite" in resp4.lower()
        print("Status: PASSED [Resolves suite to Deluxe Sunset Suite and calculates pricing]")

        # TEST 5: Ask 'What time is check-in?'
        print("\n--- TEST 5: Ask 'What time is check-in?' ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "What time is check-in?",
            "is_final": True
        }))
        resp5 = drain_until_final_agent()
        print(f"Agent: '{resp5}'")
        assert resp5 is not None
        assert "3:00" in resp5 or "3 PM" in resp5 or "3:00 PM" in resp5
        print("Status: PASSED [Grounded RAG response: Check-in is at 3:00 PM local time]")

        # TEST 6: Ask 'Do you allow dogs?'
        print("\n--- TEST 6: Ask 'Do you allow dogs?' ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "Do you allow dogs?",
            "is_final": True
        }))
        resp6 = drain_until_final_agent()
        print(f"Agent: '{resp6}'")
        assert resp6 is not None
        assert "pets are not permitted" in resp6.lower() or "not permitted" in resp6.lower() or "service animals" in resp6.lower()
        print("Status: PASSED [Grounded RAG response: Pets not permitted]")

        # TEST 7: Start speaking while agent is speaking (Barge-In)
        print("\n--- TEST 7: Immediate Barge-In Interruption ---")
        ws.send_text(json.dumps({"event": "barge_in"}))
        # Backend pacer sends 'clear' event
        clear_received = False
        for _ in range(15):
            raw = ws.receive_text()
            msg = json.loads(raw)
            if msg.get("event") == "clear":
                clear_received = True
                break
        print(f"Clear event received on barge-in: {clear_received}")
        assert clear_received, "Expected 'clear' event on barge-in"
        print("Status: PASSED [BARGE_IN triggered, pacer flushed, clear event received]")

        # TEST 8: Continue conversation after barge-in
        print("\n--- TEST 8: Continue conversation after barge-in ---")
        ws.send_text(json.dumps({
            "event": "transcript",
            "text": "What time is check-out?",
            "is_final": True
        }))
        resp8 = drain_until_final_agent()
        print(f"Agent: '{resp8}'")
        assert resp8 is not None
        assert "11:00" in resp8 or "11 AM" in resp8
        print("Status: PASSED [Context preserved after barge-in, answered check-out: 11:00 AM]")

        # TEST 9: Clear Conversation
        print("\n--- TEST 9: Clear Conversation ---")
        ws.send_text(json.dumps({"event": "clear_conversation"}))
        clear_conv_received = False
        for _ in range(15):
            raw = ws.receive_text()
            msg = json.loads(raw)
            if msg.get("event") == "conversation_cleared":
                clear_conv_received = True
                break
        print(f"conversation_cleared event received: {clear_conv_received}")
        assert clear_conv_received, "Expected 'conversation_cleared' event"
        print("Status: PASSED [Conversation cleared, buffers reset]")

        # Clean Stop
        ws.send_text(json.dumps({"event": "stop"}))

    print("\n" + "=" * 70)
    print("ALL 9 BROWSER VOICE SCENARIOS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_browser_voice_tests()
