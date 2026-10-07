import asyncio
import uuid
from datetime import date, datetime
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.db.models import Booking
from app.tools.availability import check_availability
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.orchestrator.session import SessionState
from app.llm.gemini import GeminiLLMProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider
from scratch.test_date_availability_pipeline import MockPacer

async def test_postgres_as_source_of_truth():
    print("\n--- TEST: PostgreSQL as Source of Truth for Availability ---")
    pacer = MockPacer()
    llm = GeminiLLMProvider()
    tts = ElevenLabsTTSProvider(api_key="")

    orchestrator = VoiceAgentOrchestrator(
        call_sid="test_truth_001",
        stream_sid="test_truth_001",
        pacer=pacer,
        llm_provider=llm,
        tts_provider=tts
    )
    pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

    target_ci = "2030-11-21"
    target_co = "2030-11-25"

    # Clean up any leftover test blocking bookings from PostgreSQL first
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM bookings WHERE booking_code LIKE 'BLK-%'"))
        await db.commit()

    # 1. First verify rooms are available when DB has 0 bookings for 2030-11-21 to 2030-11-25
    print("\n[STEP 1] Querying availability when DB has 0 bookings for 2030-11-21 to 2030-11-25...")
    await orchestrator.handle_final_transcript("I need a room for two guests from November 21 2030 to November 25 2030", turn_id="truth_turn_1")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task

    res1 = orchestrator._turn_last_tool_result
    msg1 = next((m["content"] for m in reversed(orchestrator.session.messages) if m["role"] == "assistant"), "")
    print(f"Tool available={res1.get('available')}, count={res1.get('count')}")
    print(f"Assistant response: '{msg1}'")
    assert res1.get("available") is True
    assert res1.get("count") == 6
    assert "available" in msg1.lower() or "options" in msg1.lower()

    # 2. Now insert bookings into PostgreSQL blocking all 6 rooms for 2030-11-21 to 2030-11-25
    print("\n[STEP 2] Inserting bookings into PostgreSQL to block ALL 6 rooms for 2030-11-21 to 2030-11-25...")
    async with AsyncSessionLocal() as db:
        rooms = (await db.execute(text("SELECT id FROM rooms"))).scalars().all()
        for idx, rid in enumerate(rooms):
            b = Booking(
                id=uuid.uuid4(),
                booking_code=f"BLK-{idx}-{uuid.uuid4().hex[:6]}",
                room_id=rid,
                check_in=date(2030, 11, 21),
                check_out=date(2030, 11, 25),
                guests=2,
                status="confirmed",
                total_price=1000.0,
                currency="USD"
            )
            db.add(b)
        await db.commit()
    print("All 6 rooms now booked in PostgreSQL for 2030-11-21 to 2030-11-25.")

    await asyncio.sleep(2.2)  # Avoid TurnManager duplicate utterance debouncing

    # 3. Query availability again for the blocked dates
    print("\n[STEP 3] Querying availability again for 2030-11-21 to 2030-11-25 (now fully booked in PostgreSQL)...")
    await orchestrator.handle_final_transcript("I need a room for two guests from November 21 2030 to November 25 2030", turn_id="truth_turn_2")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task

    res2 = orchestrator._turn_last_tool_result
    msg2 = next((m["content"] for m in reversed(orchestrator.session.messages) if m["role"] == "assistant"), "")
    print(f"Tool available={res2.get('available')}, count={res2.get('count')}")
    print(f"Assistant response: '{msg2}'")
    assert res2.get("available") is False
    assert res2.get("count") == 0
    assert "no rooms" in msg2.lower() or "do not have rooms available" in msg2.lower() or "not available" in msg2.lower()

    # 4. Clean up the test bookings from PostgreSQL
    print("\n[STEP 4] Cleaning up test blocking bookings from PostgreSQL...")
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM bookings WHERE booking_code LIKE 'BLK-%'"))
        await db.commit()
    print("Cleaned up blocking bookings.")

    await asyncio.sleep(2.2)  # Avoid TurnManager duplicate utterance debouncing

    # 5. Query availability again after cleanup
    print("\n[STEP 5] Querying availability again after cleanup...")
    await orchestrator.handle_final_transcript("I need a room for two guests from November 21 2030 to November 25 2030", turn_id="truth_turn_3")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task

    res3 = orchestrator._turn_last_tool_result
    msg3 = next((m["content"] for m in reversed(orchestrator.session.messages) if m["role"] == "assistant"), "")
    print(f"Tool available={res3.get('available')}, count={res3.get('count')}")
    print(f"Assistant response: '{msg3}'")
    assert res3.get("available") is True
    assert res3.get("count") == 6
    assert "available" in msg3.lower() or "options" in msg3.lower()

    print("\n>>> PostgreSQL AS SOURCE OF TRUTH VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(test_postgres_as_source_of_truth())
