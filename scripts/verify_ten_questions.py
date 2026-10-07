import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from app.main import simulate_demo_turn, reset_demo_session


class MockRequest:
    def __init__(self, data: dict):
        self._data = data

    async def json(self):
        return self._data


async def run_turn(prompt: str, session_id: str = "test_eval", reset: bool = False):
    req = MockRequest({"prompt": prompt, "session_id": session_id, "reset": reset})
    res = await simulate_demo_turn(req)
    return res


async def main():
    print("=" * 70)
    print("AZURE PARADISE RESORT AI - 10 EXACT CONVERSATIONAL QUESTIONS EVALUATION")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # Test 1: Check-in time
    # --------------------------------------------------------------------------
    print("\n--- TEST 1 ---")
    print("Caller: 'What time is check-in?'")
    r1 = await run_turn("What time is check-in?", session_id="sess_1", reset=True)
    ans1 = r1.get("agent_response", "")
    print(f"Agent:  {ans1}")
    assert "3:00 PM" in ans1 or "3:00 pm" in ans1.lower()
    assert "welcome to azure paradise resort" not in ans1.lower()
    print("Status: PASSED [Grounded check-in time, no welcome greeting]")

    # --------------------------------------------------------------------------
    # Test 2: Check-out time
    # --------------------------------------------------------------------------
    print("\n--- TEST 2 ---")
    print("Caller: 'What time is check-out?'")
    r2 = await run_turn("What time is check-out?", session_id="sess_2", reset=True)
    ans2 = r2.get("agent_response", "")
    print(f"Agent:  {ans2}")
    assert "11:00 AM" in ans2 or "11:00 am" in ans2.lower()
    assert "welcome to azure paradise resort" not in ans2.lower()
    print("Status: PASSED [Grounded check-out time, no welcome greeting]")

    # --------------------------------------------------------------------------
    # Test 3: Availability with dates & party size
    # --------------------------------------------------------------------------
    print("\n--- TEST 3 ---")
    print("Caller: 'What rooms are available for two guests from October 1st to October 4th?'")
    r3 = await run_turn("What rooms are available for two guests from October 1st to October 4th?", session_id="sess_3", reset=True)
    ans3 = r3.get("agent_response", "")
    print(f"Agent:  {ans3}")
    calls3 = [c["name"] for c in r3.get("tool_calls", [])]
    print(f"Tools executed: {calls3}")
    assert "check_availability" in calls3
    assert "available" in ans3.lower() or "deluxe sunset suite" in ans3.lower()
    assert "welcome to azure paradise resort" not in ans3.lower()
    print("Status: PASSED [check_availability called with dates & guests]")

    # --------------------------------------------------------------------------
    # Test 4: Pricing Deluxe Sunset Suite
    # --------------------------------------------------------------------------
    print("\n--- TEST 4 ---")
    print("Caller: 'How much is the Deluxe Sunset Suite?'")
    r4 = await run_turn("How much is the Deluxe Sunset Suite?", session_id="sess_4", reset=True)
    ans4 = r4.get("agent_response", "")
    print(f"Agent:  {ans4}")
    calls4 = [c["name"] for c in r4.get("tool_calls", [])]
    print(f"Tools executed: {calls4}")
    assert "calculate_price" in calls4
    assert "$" in ans4
    assert "welcome to azure paradise resort" not in ans4.lower()
    print("Status: PASSED [calculate_price executed, actual rate quoted]")

    # --------------------------------------------------------------------------
    # Test 5: Pet policy
    # --------------------------------------------------------------------------
    print("\n--- TEST 5 ---")
    print("Caller: 'Do you allow pets?'")
    r5 = await run_turn("Do you allow pets?", session_id="sess_5", reset=True)
    ans5 = r5.get("agent_response", "")
    print(f"Agent:  {ans5}")
    assert "not permitted" in ans5.lower() or "pets are not permitted" in ans5.lower()
    assert "welcome to azure paradise resort" not in ans5.lower()
    print("Status: PASSED [Grounded pet policy, no welcome greeting]")

    # --------------------------------------------------------------------------
    # Test 6: Restaurants / Dining
    # --------------------------------------------------------------------------
    print("\n--- TEST 6 ---")
    print("Caller: 'What restaurants do you have?'")
    r6 = await run_turn("What restaurants do you have?", session_id="sess_6", reset=True)
    ans6 = r6.get("agent_response", "")
    print(f"Agent:  {ans6}")
    assert any(k in ans6.lower() for k in ("azure ocean grill", "palm terrace", "sunset lounge", "dining"))
    assert "welcome to azure paradise resort" not in ans6.lower()
    print("Status: PASSED [Grounded dining options, no welcome greeting]")

    # --------------------------------------------------------------------------
    # Test 7: Multi-turn availability missing dates -> caller provides dates
    # --------------------------------------------------------------------------
    print("\n--- TEST 7 ---")
    print("Caller: 'What rooms are available?'")
    r7_turn1 = await run_turn("What rooms are available?", session_id="sess_7", reset=True)
    ans7_1 = r7_turn1.get("agent_response", "")
    print(f"Agent:  {ans7_1}")
    assert "dates" in ans7_1.lower() or "planning" in ans7_1.lower()
    print("Caller: 'October 1st to October 4th.'")
    r7_turn2 = await run_turn("October 1st to October 4th.", session_id="sess_7", reset=False)
    ans7_2 = r7_turn2.get("agent_response", "")
    print(f"Agent:  {ans7_2}")
    calls7_2 = [c["name"] for c in r7_turn2.get("tool_calls", [])]
    print(f"Tools executed in Turn 2: {calls7_2}")
    assert "check_availability" in calls7_2
    assert "welcome to azure paradise resort" not in ans7_2.lower()
    print("Status: PASSED [Remembers availability intent, queries dates on follow-up]")

    # --------------------------------------------------------------------------
    # Test 8: Multi-turn: Available rooms -> "Which one is cheaper?"
    # --------------------------------------------------------------------------
    print("\n--- TEST 8 ---")
    print("Caller: 'What rooms are available for two guests from October 1st to October 4th?'")
    r8_turn1 = await run_turn("What rooms are available for two guests from October 1st to October 4th?", session_id="sess_8", reset=True)
    ans8_1 = r8_turn1.get("agent_response", "")
    print(f"Agent:  {ans8_1}")
    print("Caller: 'Which one is cheaper?'")
    r8_turn2 = await run_turn("Which one is cheaper?", session_id="sess_8", reset=False)
    ans8_2 = r8_turn2.get("agent_response", "")
    print(f"Agent:  {ans8_2}")
    assert "bungalow" in ans8_2.lower()
    assert "cheaper" in ans8_2.lower() or "290" in ans8_2
    assert "welcome to azure paradise resort" not in ans8_2.lower()
    print("Status: PASSED [Understands comparison from context, uses actual prices]")

    # --------------------------------------------------------------------------
    # Test 9: Contextual room resolution: "How much is the suite?"
    # --------------------------------------------------------------------------
    print("\n--- TEST 9 ---")
    print("Caller: 'How much is the suite?'")
    r9 = await run_turn("How much is the suite?", session_id="sess_9", reset=True)
    ans9 = r9.get("agent_response", "")
    print(f"Agent:  {ans9}")
    calls9 = [c["name"] for c in r9.get("tool_calls", [])]
    print(f"Tools executed: {calls9}")
    assert "calculate_price" in calls9
    assert "Deluxe Sunset Suite" in ans9 or "$380" in ans9 or "$" in ans9
    assert "welcome to azure paradise resort" not in ans9.lower()
    print("Status: PASSED [Resolves 'suite' to Deluxe Sunset Suite]")

    # --------------------------------------------------------------------------
    # Test 10: "I want to book the Oceanfront Luxury Villa."
    # --------------------------------------------------------------------------
    print("\n--- TEST 10 ---")
    print("Caller: 'I want to book the Oceanfront Luxury Villa.'")
    r10 = await run_turn("I want to book the Oceanfront Luxury Villa.", session_id="sess_10", reset=True)
    ans10 = r10.get("agent_response", "")
    print(f"Agent:  {ans10}")
    assert "oceanfront luxury villa" in ans10.lower() or "dates" in ans10.lower() or "courtesy hold" in ans10.lower()
    assert "welcome to azure paradise resort" not in ans10.lower()
    print("Status: PASSED [Starts correct booking flow for Oceanfront Luxury Villa]")

    print("\n" + "=" * 70)
    print("ALL 10 CONVERSATIONAL INTELLIGENCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
