import asyncio
import json
import pytest
from app.utils.date_parser import parse_date_range
from app.orchestrator.session import SessionState
from app.llm.gemini import GeminiLLMProvider
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.telephony.browser_websocket import BrowserOutboundPacer
from app.tts.elevenlabs import ElevenLabsTTSProvider
from app.tools.tool_registry import tool_registry
from app.db.session import AsyncSessionLocal


@pytest.fixture(autouse=True)
async def cleanup_test_bookings():
    """Ensure test reservations and holds are isolated across test cases."""
    from sqlalchemy import text
    from app.tools.booking import HOLD_TOKENS_STORE
    HOLD_TOKENS_STORE.clear()
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM bookings WHERE check_in >= '2026-10-18' OR status = 'pending';"))
        await session.commit()
    yield
    HOLD_TOKENS_STORE.clear()
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM bookings WHERE check_in >= '2026-10-18' OR status = 'pending';"))
        await session.commit()



# ==============================================================================
# TEST 1: Date extraction
# ==============================================================================
def test_1_date_extraction():
    ci, co, err = parse_date_range("I need rooms for two guests for November 22-25")
    assert ci == "2026-11-22"
    assert co == "2026-11-25"
    assert err is None

    ci2, co2, err2 = parse_date_range("I need a room for two guests from November 22 to November 25.")
    assert ci2 == "2026-11-22"
    assert co2 == "2026-11-25"

    ci3, co3, err3 = parse_date_range("I need a room for four guests from March 10 to March 15 next year.")
    assert ci3 == "2027-03-10"
    assert co3 == "2027-03-15"

    ci4, co4, err4 = parse_date_range("I need a room from October 17 to October 21.")
    assert ci4 == "2026-10-17"
    assert co4 == "2026-10-21"

    ci5, co5, err5 = parse_date_range("Actually make it October 20 to October 25.")
    assert ci5 == "2026-10-20"
    assert co5 == "2026-10-25"


# ==============================================================================
# TEST 2: SessionState update
# ==============================================================================
def test_2_session_state_update():
    session = SessionState("call_test", "stream_test")
    session.add_user_message("I need rooms for two guests for November 22-25")
    assert session.check_in == "2026-11-22"
    assert session.check_out == "2026-11-25"
    assert session.guests == 2
    assert session.current_intent == "availability"


# ==============================================================================
# TEST 3: LLM context injection
# ==============================================================================
def test_3_llm_context_injection():
    session = SessionState("call_test", "stream_test")
    session.add_user_message("I need rooms for two guests for November 22-25")
    sys_content = session.messages[0]["content"]
    assert "Active dates: 2026-11-22 to 2026-11-25" in sys_content
    assert "Guests: 2" in sys_content


# ==============================================================================
# TEST 4: Cheapest intent
# ==============================================================================
def test_4_cheapest_intent():
    session = SessionState("call_test", "stream_test")
    session.add_user_message("I need a room for two guests from November 22 to November 25")
    # Simulate availability returned 2 rooms
    session.available_rooms = [
        {"room_id": "bungalow-garden-301", "name": "Garden Tropical Bungalow", "nightly_rate": 290.0},
        {"room_id": "suite-deluxe-201", "name": "Deluxe Sunset Suite", "nightly_rate": 380.0}
    ]
    session.add_user_message("Which one is the cheapest?")
    assert session.current_intent == "cheapest_room_comparison"
    assert session.selected_room_id == "bungalow-garden-301"
    assert session.selected_room_name == "Garden Tropical Bungalow"

    # Variations
    variations = [
        "Which room is cheapest?",
        "What's the cheapest?",
        "Give me the cheapest option.",
        "Which is the lowest price?",
        "I want the cheapest room."
    ]
    for v in variations:
        s = SessionState("call_test", "stream_test")
        s.available_rooms = session.available_rooms
        s.add_user_message(v)
        assert s.current_intent == "cheapest_room_comparison", f"Failed for variation '{v}'"


# ==============================================================================
# TEST 5: Tool argument propagation
# ==============================================================================
@pytest.mark.asyncio
async def test_5_tool_argument_propagation():
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("call_test", "stream_test", pacer=pacer, tts_provider=tts)

    # Establish context
    orch.session.check_in = "2026-11-22"
    orch.session.check_out = "2026-11-25"
    orch.session.guests = 2
    orch.session.selected_room_id = "bungalow-garden-301"
    orch.session.selected_room_name = "Garden Tropical Bungalow"

    # Simulate tool call without dates
    arguments = {"guests": 2}
    if not arguments.get("check_in") and orch.session.check_in:
        arguments["check_in"] = orch.session.check_in
    if not arguments.get("check_out") and orch.session.check_out:
        arguments["check_out"] = orch.session.check_out

    assert arguments["check_in"] == "2026-11-22"
    assert arguments["check_out"] == "2026-11-25"
    assert arguments["guests"] == 2


# ==============================================================================
# TEST 6: Booking context retention
# ==============================================================================
@pytest.mark.asyncio
async def test_6_booking_context_retention():
    session = SessionState("call_test", "stream_test")
    session.check_in = "2026-11-22"
    session.check_out = "2026-11-25"
    session.guests = 2
    session.selected_room_id = "bungalow-garden-301"
    session.selected_room_name = "Garden Tropical Bungalow"
    session.refresh_system_prompt_context()

    session.add_user_message("Book that one.")
    assert session.current_intent == "booking"
    assert session.check_in == "2026-11-22"
    assert session.check_out == "2026-11-25"
    assert session.guests == 2
    assert session.selected_room_id == "bungalow-garden-301"


# ==============================================================================
# TEST 7: Date change
# ==============================================================================
def test_7_date_change():
    session = SessionState("call_test", "stream_test")
    session.add_user_message("I need a room from October 17 to October 21.")
    assert session.check_in == "2026-10-17"
    assert session.check_out == "2026-10-21"

    # User changes dates
    session.add_user_message("Actually, make it October 20 to October 25.")
    assert session.check_in == "2026-10-20"
    assert session.check_out == "2026-10-25"
    assert session.available_rooms == []
    assert session.selected_room_id is None


# ==============================================================================
# TEST 8: Real browser voice orchestration
# ==============================================================================
@pytest.mark.asyncio
async def test_8_real_browser_voice_orchestration():
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("call_test", "stream_test", pacer=pacer, tts_provider=tts)

    await orch._process_user_turn("I need rooms for two guests for November 22-25", turn_id="turn_1")
    t1_msg = orch.session.messages[-1]["content"]
    assert "what check-in and check-out dates would you like" not in t1_msg.lower()
    assert orch.session.check_in == "2026-11-22"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2


# ==============================================================================
# TEST 9: Duplicate utterance detection
# ==============================================================================
@pytest.mark.asyncio
async def test_9_duplicate_utterance_detection():
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("call_test", "stream_test", pacer=pacer, tts_provider=tts)

    first = await orch.handle_final_transcript("I need rooms for two guests for November 22-25", turn_id="t1")
    assert first is True

    # Immediate duplicate turn_id
    second = await orch.handle_final_transcript("I need rooms for two guests for November 22-25", turn_id="t1")
    assert second is False

    # Near duplicate with new turn_id within 4s window
    third = await orch.handle_final_transcript("I need rooms for two guests for November 22-25.", turn_id="t2")
    assert third is False


# ==============================================================================
# TEST 10: Full three-turn conversation
# ==============================================================================
@pytest.mark.asyncio
async def test_10_full_three_turn_conversation():
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("call_test", "stream_test", pacer=pacer, tts_provider=tts)

    # Turn 1
    await orch._process_user_turn("I need a room for two guests from November 22 to November 25.", turn_id="turn_1")
    t1_resp = orch.session.messages[-1]["content"]
    assert "what check-in and check-out dates" not in t1_resp.lower()
    assert orch.session.check_in == "2026-11-22"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2

    # Turn 2
    await orch._process_user_turn("Which one is the cheapest?", turn_id="turn_2")
    t2_resp = orch.session.messages[-1]["content"]
    assert orch.session.current_intent == "cheapest_room_comparison"
    assert "garden tropical bungalow" in t2_resp.lower() or "bungalow" in t2_resp.lower()
    assert "290" in t2_resp or "cheapest" in t2_resp.lower()
    assert "delighted to assist you with our luxury rooms" not in t2_resp.lower()

    # Turn 3
    await orch._process_user_turn("Book that one.", turn_id="turn_3")
    t3_resp = orch.session.messages[-1]["content"]
    assert "what check-in and check-out dates" not in t3_resp.lower()
    assert orch.session.active_pending_token is not None or "courtesy hold" in t3_resp.lower()
    assert orch.session.check_in == "2026-11-22"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2


# ==============================================================================
# MANDATORY END-TO-END TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_mandatory_conversation_a():
    """
    Conversation A:
    Turn 1: "I need a room for two guests from November 22 to November 25."
    Turn 2: "Which one is the cheapest?"
    Turn 3: "Book that one."
    """
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("conv_a_call", "conv_a_stream", pacer=pacer, tts_provider=tts)

    # Turn 1
    await orch._process_user_turn("I need a room for two guests from November 22 to November 25.", turn_id="turn_a_1")
    assert orch.session.check_in == "2026-11-22"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2

    # Turn 2
    await orch._process_user_turn("Which one is the cheapest?", turn_id="turn_a_2")
    assert orch.session.current_intent == "cheapest_room_comparison"
    t2_resp = orch.session.messages[-1]["content"]
    assert "bungalow" in t2_resp.lower() or "garden" in t2_resp.lower()
    assert orch.session.selected_room_id == "bungalow-garden-301"

    # Turn 3
    await orch._process_user_turn("Book that one.", turn_id="turn_a_3")
    assert orch.session.check_in == "2026-11-22"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2
    assert orch.session.selected_room_id == "bungalow-garden-301"
    t3_resp = orch.session.messages[-1]["content"]
    assert "what check-in and check-out dates" not in t3_resp.lower()


@pytest.mark.asyncio
async def test_mandatory_conversation_b():
    """
    Conversation B:
    Turn 1: "I need a room for four guests from March 10 to March 15 next year."
    Turn 2: "Which one is the cheapest?"
    Turn 3: "Book that one."
    Verify: check_in = 2027-03-10, check_out = 2027-03-15, guests = 4
    Must NOT reuse November dates!
    """
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("conv_b_call", "conv_b_stream", pacer=pacer, tts_provider=tts)

    # Turn 1
    await orch._process_user_turn("I need a room for four guests from March 10 to March 15 next year.", turn_id="turn_b_1")
    assert orch.session.check_in == "2027-03-10"
    assert orch.session.check_out == "2027-03-15"
    assert orch.session.guests == 4

    # Turn 2
    await orch._process_user_turn("Which one is the cheapest?", turn_id="turn_b_2")
    assert orch.session.current_intent == "cheapest_room_comparison"
    assert orch.session.check_in == "2027-03-10"
    assert orch.session.check_out == "2027-03-15"
    assert orch.session.guests == 4

    # Turn 3
    await orch._process_user_turn("Book that one.", turn_id="turn_b_3")
    assert orch.session.check_in == "2027-03-10"
    assert orch.session.check_out == "2027-03-15"
    assert orch.session.guests == 4
    t3_resp = orch.session.messages[-1]["content"]
    assert "what check-in and check-out dates" not in t3_resp.lower()


@pytest.mark.asyncio
async def test_mandatory_conversation_c():
    """
    Conversation C:
    Turn 1: "I need a room from October 17 to October 21."
    Turn 2: "Actually make it October 20 to October 25."
    Turn 3: "Which one is cheapest?"
    Verify: October 20 -> October 25, NOT October 17 -> October 21.
    """
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("conv_c_call", "conv_c_stream", pacer=pacer, tts_provider=tts)

    # Turn 1
    await orch._process_user_turn("I need a room from October 17 to October 21.", turn_id="turn_c_1")
    assert orch.session.check_in == "2026-10-17"
    assert orch.session.check_out == "2026-10-21"

    # Turn 2
    await orch._process_user_turn("Actually make it October 20 to October 25.", turn_id="turn_c_2")
    assert orch.session.check_in == "2026-10-20"
    assert orch.session.check_out == "2026-10-25"

    # Turn 3
    await orch._process_user_turn("Which one is cheapest?", turn_id="turn_c_3")
    assert orch.session.current_intent == "cheapest_room_comparison"
    assert orch.session.check_in == "2026-10-20"
    assert orch.session.check_out == "2026-10-25"


# ==============================================================================
# REGRESSION TESTS: BOOKING CONTEXT & PRICE DETAILS RETENTION
# ==============================================================================

@pytest.mark.asyncio
async def test_regression_1_cheapest_book_confirm_price_details():
    """
    Regression Test 1:
    1. Guest asks for 2 guests Nov 21–25.
    2. Guest asks cheapest.
    3. Guest says 'book that one'.
    4. Guest says 'is confirmed'.
    5. Guest asks 'can you share me the price details about'.
    Verifies that Garden Tropical Bungalow is preserved, never substituted with Deluxe Sunset Suite.
    """
    async def dummy_send(m): pass
    pacer = BrowserOutboundPacer("test_stream", dummy_send)
    pacer.start()
    tts = ElevenLabsTTSProvider(api_key="")
    orch = VoiceAgentOrchestrator("reg_call_1", "reg_stream_1", pacer=pacer, tts_provider=tts)

    # 1. Dates
    await orch._process_user_turn("I need a room for two guests from November 21 to November 25.", turn_id="t1")
    assert orch.session.check_in == "2026-11-21"
    assert orch.session.check_out == "2026-11-25"
    assert orch.session.guests == 2

    # 2. Cheapest
    await orch._process_user_turn("Which one is the cheapest?", turn_id="t2")
    assert orch.session.selected_room_id == "bungalow-garden-301"
    t2_resp = orch.session.messages[-1]["content"].lower()
    assert "garden tropical bungalow" in t2_resp or "bungalow" in t2_resp
    assert "290" in t2_resp

    # 3. Book that one
    await orch._process_user_turn("Book that one.", turn_id="t3")
    assert orch.session.selected_room_id == "bungalow-garden-301"
    t3_resp = orch.session.messages[-1]["content"].lower()
    assert "hold" in t3_resp or "reserve" in t3_resp
    assert "what check-in and check-out dates" not in t3_resp

    # 4. Confirm reservation
    await orch._process_user_turn("is confirmed", turn_id="t4")
    assert orch.session.confirmed_booking_id is not None
    assert orch.session.confirmed_booking_id.lower() != "confirmed"
    assert orch.session.confirmed_booking_id.startswith("RES-")
    t4_resp = orch.session.messages[-1]["content"]
    assert orch.session.confirmed_booking_id in t4_resp
    assert "number confirmed" not in t4_resp.lower()

    # 5. Price details
    await orch._process_user_turn("can you share me the price details about", turn_id="t5")
    t5_resp = orch.session.messages[-1]["content"].lower()
    # Must NOT substitute Deluxe Sunset Suite ($380)
    assert "deluxe sunset suite" not in t5_resp
    assert "380" not in t5_resp
    # Must retain Garden Tropical Bungalow ($290)
    assert "garden tropical bungalow" in t5_resp or "bungalow" in t5_resp
    assert "290" in t5_resp
    # Must include required price breakdown components
    assert "1,160" in t5_resp or "1160" in t5_resp  # lodging subtotal
    assert "180" in t5_resp  # resort fee ($45 * 4)
    assert "160.80" in t5_resp or "161" in t5_resp  # taxes
    assert "1,500.80" in t5_resp or "1500.80" in t5_resp  # grand total


@pytest.mark.asyncio
async def test_regression_2_price_details_after_confirmed_booking():
    """
    Regression Test 2:
    Tests various price-detail question phrasings after a confirmed booking:
    'price details', 'how much is my booking', 'what is the total', 'breakdown', 'how much do I pay'.
    All must use the current confirmed booking, never generic room selection.
    """
    from app.tools.booking import create_booking, save_booking
    async with AsyncSessionLocal() as session:
        hold_res = await create_booking(
            room_id="bungalow-garden-301",
            guest_name="Valued Guest",
            check_in="2026-11-21",
            check_out="2026-11-25",
            guests=2,
            db_session=session
        )
        conf_res = await save_booking(hold_res["pending_token"], db_session=session)
        await session.commit()

    test_queries = [
        "price details",
        "how much is my booking",
        "what is the total",
        "breakdown",
        "how much do I pay",
    ]

    for q in test_queries:
        async def dummy_send(m): pass
        pacer = BrowserOutboundPacer("test_stream", dummy_send)
        pacer.start()
        tts = ElevenLabsTTSProvider(api_key="")
        orch = VoiceAgentOrchestrator("reg_call_2", "reg_stream_2", pacer=pacer, tts_provider=tts)

        orch.session.check_in = "2026-11-21"
        orch.session.check_out = "2026-11-25"
        orch.session.guests = 2
        orch.session.selected_room_id = "bungalow-garden-301"
        orch.session.selected_room_name = "Garden Tropical Bungalow"
        orch.session.confirmed_booking_id = conf_res["booking_code"]
        orch.session.confirmed_booking_data = conf_res
        orch.session.refresh_system_prompt_context()

        await orch._process_user_turn(q, turn_id=f"turn_{q.replace(' ', '_')}")
        resp = orch.session.messages[-1]["content"].lower()

        assert "deluxe sunset suite" not in resp, f"Failed for query: {q}"
        assert "garden tropical bungalow" in resp or "bungalow" in resp, f"Failed for query: {q}"
        assert "1,500.80" in resp or "1500.80" in resp, f"Failed for query: {q}"


@pytest.mark.asyncio
async def test_regression_3_price_details_same_room_id_as_booking():
    """
    Regression Test 3:
    calculate_price tool call must reference the EXACT same room_id as the booking,
    never substituting another room.
    """
    from app.tools.pricing import calculate_price
    from app.tools.booking import create_booking, save_booking

    async with AsyncSessionLocal() as session:
        hold_res = await create_booking(
            room_id="villa-ocean-101",
            guest_name="VIP Guest",
            check_in="2026-12-01",
            check_out="2026-12-05",
            guests=4,
            db_session=session
        )
        conf_res = await save_booking(hold_res["pending_token"], db_session=session)
        await session.commit()

        # Calculate price referencing the confirmed booking_id
        price_result = await calculate_price(
            room_id="villa-ocean-101",
            check_in="2026-12-01",
            check_out="2026-12-05",
            booking_id=conf_res["booking_code"],
            db_session=session
        )

        assert price_result["ok"] is True
        assert price_result["room_id"] == "villa-ocean-101"
        assert price_result["room_name"] == "Oceanfront Luxury Villa"
        assert price_result["room_type"] == "villa"
        assert price_result["check_in"] == "2026-12-01"
        assert price_result["check_out"] == "2026-12-05"
        assert price_result["number_of_nights"] == 4
        assert price_result["nightly_rate"] == 650.0
        assert price_result["lodging_subtotal"] == 2600.0
        assert price_result["resort_fee"] == 180.0
        assert price_result["taxes"] == 333.6
        assert price_result["grand_total"] == 3113.6
        assert price_result["booking_id"] == conf_res["booking_code"]
        assert price_result["confirmation_number"] == conf_res["booking_code"]


@pytest.mark.asyncio
async def test_regression_4_confirmation_number_real_generated_value():
    """
    Regression Test 4:
    Confirmation number must be a real generated value (RES-XXXXXXXX),
    never literal string 'confirmed'.
    """
    from app.tools.booking import create_booking, save_booking

    async with AsyncSessionLocal() as session:
        hold = await create_booking(
            room_id="bungalow-garden-301",
            check_in="2026-11-21",
            check_out="2026-11-25",
            db_session=session
        )
        conf = await save_booking(hold["pending_token"], db_session=session)
        await session.commit()

    assert conf["ok"] is True
    assert conf["booking_code"] != "confirmed"
    assert conf["confirmation_number"] != "confirmed"
    assert conf["booking_code"].startswith("RES-")
    assert len(conf["booking_code"]) == 12  # "RES-" + 8 hex chars
    assert conf["confirmation_number"] == conf["booking_code"]

