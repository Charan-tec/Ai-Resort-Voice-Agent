import asyncio
import pytest
import uuid
from datetime import date
from sqlalchemy import text
from app.utils.date_parser import parse_date_range, get_reference_date
from app.tools.availability import check_availability
from app.orchestrator.session import SessionState
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.llm.gemini import GeminiLLMProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider
from app.db.session import AsyncSessionLocal
from app.db.models import Booking
from scratch.test_date_availability_pipeline import MockPacer


# 1. Regression Test: Explicit Year
def test_explicit_year_preserved():
    ref_date = date(2026, 10, 7)
    # 2027
    ci, co, err = parse_date_range("I need a room for two guests from November 21 2027 to November 25 2027", reference_date=ref_date)
    assert err is None
    assert ci == "2027-11-21"
    assert co == "2027-11-25"

    # 2030
    ci, co, err = parse_date_range("I need a room for two guests from November 21 2030 to November 25 2030", reference_date=ref_date)
    assert err is None
    assert ci == "2030-11-21"
    assert co == "2030-11-25"

    # Arbitrary distant future year 2035
    ci, co, err = parse_date_range("I need a room for two guests from November 21 2035 to November 25 2035", reference_date=ref_date)
    assert err is None
    assert ci == "2035-11-21"
    assert co == "2035-11-25"


# 2. Regression Test: Implicit Year Upcoming
def test_implicit_year_upcoming():
    ref_date = date(2026, 10, 7)
    # November is upcoming in 2026
    ci, co, err = parse_date_range("I need a room for two guests from November 21 to November 25", reference_date=ref_date)
    assert err is None
    assert ci == "2026-11-21"
    assert co == "2026-11-25"


# 3. Regression Test: Year Rollover
def test_year_rollover_elapsed_month():
    ref_date = date(2026, 10, 7)
    # January has already passed in 2026 -> rolls over to 2027
    ci, co, err = parse_date_range("I need a room for two guests from January 10 to January 15", reference_date=ref_date)
    assert err is None
    assert ci == "2027-01-10"
    assert co == "2027-01-15"


# 4. Regression Test: Cross-Year Date Range Rollover
def test_cross_year_rollover():
    ref_date = date(2026, 10, 7)
    # Cross-year rollover with explicit year
    ci, co, err = parse_date_range("I need a room for two guests from December 28 2027 to January 3 2028", reference_date=ref_date)
    assert err is None
    assert ci == "2027-12-28"
    assert co == "2028-01-03"

    # Cross-year rollover implicit
    ci2, co2, err2 = parse_date_range("from December 28 to January 3", reference_date=ref_date)
    assert err2 is None
    assert ci2 == "2026-12-28"
    assert co2 == "2027-01-03"


# 5. Regression Test: Leap Year vs Non-Leap Year
def test_leap_year_handling():
    ref_date = date(2026, 10, 7)
    # 2028 is a leap year -> February 29 is valid
    ci, co, err = parse_date_range("I need a room for two guests from February 28 2028 to March 2 2028", reference_date=ref_date)
    assert err is None
    assert ci == "2028-02-28"
    assert co == "2028-03-02"

    ci_leap, co_leap, err_leap = parse_date_range("from February 29 2028 to March 2 2028", reference_date=ref_date)
    assert err_leap is None
    assert ci_leap == "2028-02-29"
    assert co_leap == "2028-03-02"

    # 2027 is NOT a leap year -> February 29 is INVALID and MUST be rejected
    ci_bad, co_bad, err_bad = parse_date_range("I need a room for two guests from February 29 2027 to March 2 2027", reference_date=ref_date)
    assert err_bad is not None
    assert "invalid calendar date" in err_bad.lower()
    assert ci_bad is None
    assert co_bad is None


# 6. Regression Test: Reversed Date Range
def test_reversed_date_range():
    ref_date = date(2026, 10, 7)
    ci, co, err = parse_date_range("I need a room for two guests from November 25 to November 21", reference_date=ref_date)
    assert err is not None
    assert "after check-in" in err.lower()
    assert ci is None
    assert co is None


# 7. Regression Test: PostgreSQL check_availability receives exact dates and queries DB
@pytest.mark.asyncio
async def test_check_availability_exact_dates_query():
    # 2030 dates
    res = await check_availability(check_in="2030-11-21", check_out="2030-11-25", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["check_in"] == "2030-11-21"
    assert res["check_out"] == "2030-11-25"
    assert res["nights"] == 4
    assert res["count"] == 6

    # 2035 dates
    res35 = await check_availability(check_in="2035-11-21", check_out="2035-11-25", guests=2)
    assert res35["ok"] is True
    assert res35["available"] is True
    assert res35["check_in"] == "2035-11-21"
    assert res35["check_out"] == "2035-11-25"


# 8. Regression Test: Fresh Availability Query for Every New Date Range in Orchestrator
@pytest.mark.asyncio
async def test_fresh_availability_query_per_turn():
    pacer = MockPacer()
    orchestrator = VoiceAgentOrchestrator(
        call_sid="fresh_query_audit",
        stream_sid="fresh_query_audit",
        pacer=pacer,
        llm_provider=GeminiLLMProvider(),
        tts_provider=ElevenLabsTTSProvider(api_key="")
    )
    pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

    # Query Turn 1: 2027
    await orchestrator.handle_final_transcript("I need a room for two guests from November 21 2027 to November 25 2027", turn_id="turn_fresh_1")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task
    assert orchestrator._turn_last_tool_args is not None
    assert orchestrator._turn_last_tool_args["check_in"] == "2027-11-21"
    assert orchestrator._turn_last_tool_args["check_out"] == "2027-11-25"
    assert orchestrator.session.check_in == "2027-11-21"

    await asyncio.sleep(2.1)

    # Query Turn 2: 2030
    await orchestrator.handle_final_transcript("What about from November 21 2030 to November 25 2030?", turn_id="turn_fresh_2")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task
    assert orchestrator._turn_last_tool_args is not None
    assert orchestrator._turn_last_tool_args["check_in"] == "2030-11-21"
    assert orchestrator._turn_last_tool_args["check_out"] == "2030-11-25"
    assert orchestrator.session.check_in == "2030-11-21"

    await asyncio.sleep(2.1)

    # Query Turn 3: 2035
    await orchestrator.handle_final_transcript("Can you check from November 21 2035 to November 25 2035?", turn_id="turn_fresh_3")
    await asyncio.sleep(0.4)
    if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
        await orchestrator._active_llm_task
    assert orchestrator._turn_last_tool_args is not None
    assert orchestrator._turn_last_tool_args["check_in"] == "2035-11-21"
    assert orchestrator._turn_last_tool_args["check_out"] == "2035-11-25"
    assert orchestrator.session.check_in == "2035-11-21"


# 9. Regression Test: PostgreSQL Source of Truth
@pytest.mark.asyncio
async def test_postgresql_authoritative_availability():
    # When all rooms are blocked in DB for 2032-05-10 to 2032-05-14
    ci = "2032-05-10"
    co = "2032-05-14"

    async with AsyncSessionLocal() as db:
        rooms = (await db.execute(text("SELECT id FROM rooms"))).scalars().all()
        for idx, rid in enumerate(rooms):
            b = Booking(
                id=uuid.uuid4(),
                booking_code=f"REGR-{idx}-{uuid.uuid4().hex[:6]}",
                room_id=rid,
                check_in=date(2032, 5, 10),
                check_out=date(2032, 5, 14),
                guests=2,
                status="confirmed",
                total_price=1000.0,
                currency="USD"
            )
            db.add(b)
        await db.commit()

    try:
        # Check availability should return available=False
        res = await check_availability(check_in=ci, check_out=co, guests=2)
        assert res["available"] is False
        assert res["count"] == 0
        assert res["available_rooms"] == []
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM bookings WHERE booking_code LIKE 'REGR-%'"))
            await db.commit()

    # After cleanup, check availability should return available=True
    res_after = await check_availability(check_in=ci, check_out=co, guests=2)
    assert res_after["available"] is True
    assert res_after["count"] == 6
