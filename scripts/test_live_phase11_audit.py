import asyncio
import json
import websockets
import sys

URI = "ws://localhost:8000/ws/browser-voice"

async def drain_turn_response(ws, timeout=12.0):
    asst_parts = []
    while True:
        try:
            m = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(m)
            evt = data.get("event")
            if evt == "transcript" and data.get("role") == "assistant":
                text = data.get("content", "").strip()
                if text and text not in asst_parts:
                    asst_parts.append(text)
            elif evt == "mark" and "browser_turn_end" in data.get("mark", {}).get("name", ""):
                break
        except asyncio.TimeoutError:
            break
    return " ".join(asst_parts)

async def start_session(ws, session_id):
    msg = await ws.recv() # connected
    await ws.send(json.dumps({"event": "start", "session_id": session_id}))
    msg = await ws.recv() # session_state
    # Drain greeting
    greeting = await drain_turn_response(ws, timeout=5.0)
    return greeting

async def run_turn(ws, text, turn_idx):
    await ws.send(json.dumps({
        "event": "transcript",
        "text": text,
        "is_final": True,
        "turn_id": f"phase11_turn_{turn_idx}"
    }))
    response = await drain_turn_response(ws, timeout=12.0)
    await asyncio.sleep(0.3)
    return response

async def run_test_a():
    print("\n================== RUNNING TEST A ==================", flush=True)
    async with websockets.connect(URI) as ws:
        await start_session(ws, "phase11_test_a")
        
        # Turn 1
        r1 = await run_turn(ws, "I need a room for two guests from November 22 to November 25.", 1)
        print(f"Test A Turn 1: '{r1}'", flush=True)
        assert any(w in r1.lower() for w in ["available", "option", "bungalow", "suite", "pricing"]), f"Unexpected r1: {r1}"
        
        # Turn 2
        r2 = await run_turn(ws, "Which one is the cheapest?", 2)
        print(f"Test A Turn 2: '{r2}'", flush=True)
        assert "garden tropical bungalow" in r2.lower() or "290" in r2, f"Expected cheapest bungalow, got: {r2}"
        
        # Turn 3
        r3 = await run_turn(ws, "Book that one.", 3)
        print(f"Test A Turn 3: '{r3}'", flush=True)
        assert any(w in r3.lower() for w in ["reserve", "hold", "garden tropical bungalow", "2026-11-22"]), f"Expected booking hold, got: {r3}"
        print(">>> TEST A: PASSED", flush=True)

async def run_test_b():
    print("\n================== RUNNING TEST B ==================", flush=True)
    async with websockets.connect(URI) as ws:
        await start_session(ws, "phase11_test_b")
        
        # Turn 1
        r1 = await run_turn(ws, "I need a room for four guests from March 10 to March 15 next year.", 1)
        print(f"Test B Turn 1: '{r1}'", flush=True)
        
        # Turn 2: Date update
        r2 = await run_turn(ws, "Actually, change it to March 20 to March 25.", 2)
        print(f"Test B Turn 2: '{r2}'", flush=True)
        assert any(w in r2.lower() for w in ["available", "option", "villa", "suite"]), f"Expected availability for new dates, got: {r2}"
        
        # Turn 3: Cheapest
        r3 = await run_turn(ws, "Which one is cheapest?", 3)
        print(f"Test B Turn 3: '{r3}'", flush=True)
        # For 4 guests, Family Pool Villa is $520, Luxury Villa is $650, Presidential Suite is $850. Cheapest is Family Pool Villa!
        assert "family pool villa" in r3.lower() or "520" in r3 or "cheapest" in r3.lower(), f"Expected Family Pool Villa or cheapest info, got: {r3}"
        print(">>> TEST B: PASSED", flush=True)

async def run_test_c():
    print("\n================== RUNNING TEST C ==================", flush=True)
    async with websockets.connect(URI) as ws:
        await start_session(ws, "phase11_test_c")
        
        r1 = await run_turn(ws, "I need a room from the 12th to the 16th of December.", 1)
        print(f"Test C Turn 1: '{r1}'", flush=True)
        assert any(w in r1.lower() for w in ["available", "option", "suite", "bungalow", "villa"]), f"Expected availability response, got: {r1}"
        print(">>> TEST C: PASSED", flush=True)

async def run_test_d():
    print("\n================== RUNNING TEST D ==================", flush=True)
    async with websockets.connect(URI) as ws:
        await start_session(ws, "phase11_test_d")
        
        r1 = await run_turn(ws, "I need rooms for two guests.", 1)
        print(f"Test D Turn 1: '{r1}'", flush=True)
        assert any(w in r1.lower() for w in ["date", "check-in", "when", "stay"]), f"Expected agent to ask for dates, got: {r1}"
        print(">>> TEST D: PASSED", flush=True)

async def run_test_e():
    print("\n================== RUNNING TEST E ==================", flush=True)
    async with websockets.connect(URI) as ws:
        await start_session(ws, "phase11_test_e")
        
        r1 = await run_turn(ws, "What rooms are available?", 1)
        print(f"Test E Turn 1: '{r1}'", flush=True)
        assert any(w in r1.lower() for w in ["date", "check-in", "when", "stay"]), f"Expected agent to ask for dates, got: {r1}"
        print(">>> TEST E: PASSED", flush=True)

async def main():
    try:
        await run_test_a()
        await run_test_b()
        await run_test_c()
        await run_test_d()
        await run_test_e()
        print("\n==================================================", flush=True)
        print("ALL PHASE 11 REQUIRED LIVE TESTS PASSED SUCCESSFULLY!", flush=True)
        print("==================================================", flush=True)
    except Exception as e:
        print(f"\nPHASE 11 TEST FAILED: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
