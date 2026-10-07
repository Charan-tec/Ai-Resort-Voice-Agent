import json
import pytest
from datetime import date
from sqlalchemy import text, delete, select
from app.db.session import AsyncSessionLocal
from app.db.models import Room, Booking, Customer
from app.tools.availability import check_availability, RESORT_ROOMS
from app.tools.pricing import calculate_price
from app.tools.booking import create_booking, save_booking
from app.utils.date_parser import parse_date_range
from app.orchestrator.session import SessionState
from app.llm.gemini import GeminiLLMProvider
from app.tools.tool_registry import tool_registry


@pytest.fixture(autouse=True)
async def cleanup_test_bookings():
    """Ensure test reservations are cleaned up before and after each test."""
    async with AsyncSessionLocal() as session:
        cust_sub = select(Customer.id).where(Customer.email.in_(["elena@example.com", "jordan@example.com", "guest@azureparadise-resort.com"]))
        await session.execute(delete(Booking).where(Booking.customer_id.in_(cust_sub)))
        await session.execute(delete(Customer).where(Customer.email.in_(["elena@example.com", "jordan@example.com", "guest@azureparadise-resort.com"])))
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        cust_sub = select(Customer.id).where(Customer.email.in_(["elena@example.com", "jordan@example.com", "guest@azureparadise-resort.com"]))
        await session.execute(delete(Booking).where(Booking.customer_id.in_(cust_sub)))
        await session.execute(delete(Customer).where(Customer.email.in_(["elena@example.com", "jordan@example.com", "guest@azureparadise-resort.com"])))
        await session.commit()



# ==============================================================================
# Part 1: Room Inventory Verification
# ==============================================================================
@pytest.mark.asyncio
async def test_room_inventory_has_six_rooms():
    """Verify exactly 6 active rooms exist in PostgreSQL without duplicates."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, name, max_occupancy, base_rate FROM rooms WHERE is_active = true ORDER BY base_rate")
        )
        rooms = result.fetchall()
        assert len(rooms) == 6, f"Expected 6 rooms, found {len(rooms)}"

        room_dict = {r[0]: {"name": r[1], "capacity": r[2], "rate": r[3]} for r in rooms}
        
        # Verify 3 original rooms
        assert "villa-ocean-101" in room_dict
        assert room_dict["villa-ocean-101"]["rate"] == 650.0
        assert room_dict["villa-ocean-101"]["capacity"] == 4

        assert "suite-deluxe-201" in room_dict
        assert room_dict["suite-deluxe-201"]["rate"] == 380.0
        assert room_dict["suite-deluxe-201"]["capacity"] == 2

        assert "bungalow-garden-301" in room_dict
        assert room_dict["bungalow-garden-301"]["rate"] == 290.0
        assert room_dict["bungalow-garden-301"]["capacity"] == 3

        # Verify 3 new rooms
        assert "suite-presidential-401" in room_dict
        assert room_dict["suite-presidential-401"]["rate"] == 850.0
        assert room_dict["suite-presidential-401"]["capacity"] == 4

        assert "villa-family-501" in room_dict
        assert room_dict["villa-family-501"]["rate"] == 520.0
        assert room_dict["villa-family-501"]["capacity"] == 6

        assert "suite-premium-302" in room_dict
        assert room_dict["suite-premium-302"]["rate"] == 450.0
        assert room_dict["suite-premium-302"]["capacity"] == 3


# ==============================================================================
# Part 4: Date Parsing Tests
# ==============================================================================
def test_date_parser_natural_language():
    """Verify natural language date parsing to YYYY-MM-DD."""
    # A. Oct 17 to Oct 21 2026
    ci, co, err = parse_date_range("October 17 to October 21")
    assert err is None
    assert ci == "2026-10-17"
    assert co == "2026-10-21"

    # B. Nov 20 to Nov 25 2026
    ci, co, err = parse_date_range("November 20 to November 25")
    assert err is None
    assert ci == "2026-11-20"
    assert co == "2026-11-25"

    # C. Mar 10 to Mar 15 2027 ("next year")
    ci, co, err = parse_date_range("March 10 to March 15 next year")
    assert err is None
    assert ci == "2027-03-10"
    assert co == "2027-03-15"

    # D. Dec 28 2026 to Jan 3 2027 (cross-year rollover)
    ci, co, err = parse_date_range("December 28 to January 3")
    assert err is None
    assert ci == "2026-12-28"
    assert co == "2027-01-03"

    # E. Single-month numeric / ordinal format
    ci, co, err = parse_date_range("from the 12th to the 16th of November")
    assert err is None
    assert ci == "2026-11-12"
    assert co == "2026-11-16"

    ci, co, err = parse_date_range("from 11/20 to 11/25")
    assert err is None
    assert ci == "2026-11-20"
    assert co == "2026-11-25"

    ci, co, err = parse_date_range("Book me a room from December 5 to December 8")
    assert err is None
    assert ci == "2026-12-05"
    assert co == "2026-12-08"

    # F. Relative phrases: "next weekend" and "this weekend"
    ci, co, err = parse_date_range("Can I get a room next weekend?")
    assert err is None
    assert ci is not None and co is not None
    assert ci < co

    ci, co, err = parse_date_range("Can I get a room this weekend?")
    assert err is None
    assert ci is not None and co is not None
    assert ci < co

    # H. Invalid calendar date
    ci, co, err = parse_date_range("February 30 to February 32")
    assert err is not None
    assert "invalid calendar date" in err.lower()

    # I. Checkout before check-in
    ci, co, err = parse_date_range("October 21 to October 17")
    assert err is not None
    assert "after check-in" in err.lower()

    # J. Past date
    ci, co, err = parse_date_range("May 10 to May 15 2024")
    assert err is not None
    assert "past" in err.lower()


# ==============================================================================
# Part 10: Date Ranges & Availability Scenarios
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_1_current_month_dates():
    """Scenario 1: Current-month dates (e.g. October 2026)."""
    res = await check_availability("2026-10-25", "2026-10-29", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] > 0
    assert len(res["available_rooms"]) > 0


@pytest.mark.asyncio
async def test_scenario_2_next_month_dates():
    """Scenario 2: Next-month dates (e.g. November 2026)."""
    res = await check_availability("2026-11-20", "2026-11-25", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] > 0
    # At least the suites and bungalows should be available
    room_ids = [r["room_id"] for r in res["available_rooms"]]
    assert "suite-deluxe-201" in room_ids
    assert "bungalow-garden-301" in room_ids


@pytest.mark.asyncio
async def test_scenario_3_several_months_future():
    """Scenario 3: Date several months in the future (e.g. January or March 2027)."""
    res = await check_availability("2027-03-10", "2027-03-15", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] == 6  # All 6 rooms available far in future


@pytest.mark.asyncio
async def test_scenario_4_no_overlapping_booking():
    """Scenario 4: Date range with no overlapping booking."""
    # Test non-overlapping contiguous boundaries: [check_in, check_out)
    # A booking exists for villa-ocean-101 Oct 10 -> Oct 14.
    # An inquiry for Oct 14 -> Oct 18 must NOT overlap Oct 10 -> Oct 14 for that room.
    res = await check_availability("2026-10-14", "2026-10-15", guests=2, room_type="villa-ocean-101")
    assert res["ok"] is True
    # Oct 14 to Oct 15 is free (next booking starts Oct 15)
    assert res["available"] is True
    assert any(r["room_id"] == "villa-ocean-101" for r in res["available_rooms"])


@pytest.mark.asyncio
async def test_scenario_5_overlapping_existing_booking():
    """Scenario 5: Date range overlapping an existing confirmed booking."""
    # villa-ocean-101 is booked 2026-10-10 -> 2026-10-14
    res = await check_availability("2026-10-11", "2026-10-13", room_type="villa-ocean-101")
    assert res["ok"] is True
    assert res["available"] is False
    assert len(res["available_rooms"]) == 0


@pytest.mark.asyncio
async def test_scenario_specific_dates_oct_10_to_14():
    """Explicit requested test: October 10 2026 -> October 14 2026."""
    res = await check_availability("2026-10-10", "2026-10-14", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] >= 4
    room_ids = [r["room_id"] for r in res["available_rooms"]]
    # villa-ocean-101 is booked, but other rooms MUST be available
    assert "villa-ocean-101" not in room_ids
    assert "suite-deluxe-201" in room_ids
    assert "bungalow-garden-301" in room_ids
    assert "villa-family-501" in room_ids


@pytest.mark.asyncio
async def test_scenario_specific_dates_oct_17_to_21():
    """Explicit requested test: October 17 2026 -> October 21 2026."""
    res = await check_availability("2026-10-17", "2026-10-21", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] >= 4


# ==============================================================================
# Part 5: Guest Capacity Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_guest_capacity_two_guests():
    """6. 2 guests -> rooms with capacity >= 2."""
    res = await check_availability("2027-02-01", "2027-02-05", guests=2)
    assert res["ok"] is True
    # All 6 rooms have capacity >= 2
    assert res["count"] == 6


@pytest.mark.asyncio
async def test_guest_capacity_four_guests():
    """7. 4 guests -> rooms with capacity >= 4."""
    res = await check_availability("2027-02-01", "2027-02-05", guests=4)
    assert res["ok"] is True
    # Qualifying rooms: villa-ocean-101 (4), suite-presidential-401 (4), villa-family-501 (6)
    room_ids = [r["room_id"] for r in res["available_rooms"]]
    assert len(room_ids) == 3
    assert set(room_ids) == {"villa-ocean-101", "suite-presidential-401", "villa-family-501"}


@pytest.mark.asyncio
async def test_guest_capacity_six_guests():
    """8. 6 guests -> Family Pool Villa should qualify."""
    res = await check_availability("2027-02-01", "2027-02-05", guests=6)
    assert res["ok"] is True
    assert res["count"] == 1
    assert res["available_rooms"][0]["room_id"] == "villa-family-501"
    assert res["available_rooms"][0]["name"] == "Family Pool Villa"


@pytest.mark.asyncio
async def test_guest_capacity_seven_guests_exceeds_max():
    """7 guests -> exceeds maximum room capacity of 6, returns informative message."""
    res = await check_availability("2027-02-01", "2027-02-05", guests=7)
    assert res["ok"] is True
    assert res["available"] is False
    assert res["count"] == 0
    assert "exceeds maximum room capacity of 6" in res["message"]


# ==============================================================================
# Part 6: Pricing Dynamic Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_calculate_price_dynamic_any_dates():
    """calculate_price works for ANY valid requested date range."""
    # 4 nights in Family Pool Villa ($520/night)
    # Base: 4 * 520 = 2080
    # Resort fee: 4 * 45 = 180
    # Subtotal: 2260, Tax (12%): 271.20, Total: 2531.20
    res = await calculate_price(
        room_id="villa-family-501",
        check_in="2026-11-20",
        check_out="2026-11-24",
        add_ons=[]
    )
    assert res["ok"] is True
    assert res["nights"] == 4
    assert res["nightly_rate"] == 520.0
    assert res["subtotal"] == 2080.0
    assert res["total_price"] == 2531.2


# ==============================================================================
# Part 7: Booking Scenarios (New Rooms & Cheapest Room)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_booking_new_room_presidential_suite():
    """9. Booking one of the new rooms (Presidential Ocean Suite)."""
    # 1. Check availability
    ci = "2027-04-10"
    co = "2027-04-14"
    avail = await check_availability(ci, co, guests=4, room_type="suite-presidential-401")
    assert avail["available"] is True

    # 2. Price calculation
    price = await calculate_price(room_id="suite-presidential-401", check_in=ci, check_out=co)
    assert price["ok"] is True

    # 3. Create booking hold
    booking_hold = await create_booking(
        room_id="suite-presidential-401",
        guest_name="Elena Rostova",
        guest_email="elena@example.com",
        guest_phone="+15551234567",
        check_in=ci,
        check_out=co,
        guests=4,
        total_price=price["total_price"]
    )
    assert booking_hold["ok"] is True
    assert "pending_token" in booking_hold

    # 4. Save/Confirm booking
    confirm = await save_booking(
        pending_token=booking_hold["pending_token"]
    )
    assert confirm["ok"] is True
    assert confirm["status"] == "confirmed"
    assert "booking_code" in confirm
    assert confirm["booking_code"].startswith("RES-")


@pytest.mark.asyncio
async def test_scenario_cheapest_room_booking():
    """10. Cheapest-room booking."""
    ci = "2027-05-10"
    co = "2027-05-14"
    # Check availability for 2 guests
    avail = await check_availability(ci, co, guests=2)
    assert avail["available"] is True
    assert "cheapest_room" in avail
    cheapest = avail["cheapest_room"]
    # Cheapest for 2 guests is Garden Tropical Bungalow ($290/night)
    assert cheapest["room_id"] == "bungalow-garden-301"
    assert cheapest["nightly_rate"] == 290.0

    # Calculate price for cheapest
    pricing = await calculate_price(room_id=cheapest["room_id"], check_in=ci, check_out=co)
    assert pricing["ok"] is True

    # Book cheapest room
    booking_hold = await create_booking(
        room_id=cheapest["room_id"],
        guest_name="Jordan Lee",
        guest_email="jordan@example.com",
        guest_phone="+15559876543",
        check_in=ci,
        check_out=co,
        guests=2,
        total_price=pricing["total_price"]
    )
    assert booking_hold["ok"] is True

    confirm = await save_booking(
        pending_token=booking_hold["pending_token"]
    )
    assert confirm["ok"] is True
    assert confirm["status"] == "confirmed"


# ==============================================================================
# Part 8: Context Retention in Session State
# ==============================================================================
def test_conversation_context_retention():
    """Verify session retains dates, guests, and selected rooms across utterances."""
    session = SessionState(call_sid="ctx_test_1", stream_sid="ctx_stream_1")
    
    # Turn 1: User gives dates and guests
    session.update_context_from_utterance("I need a room for two guests from November 10 to November 14.")
    assert session.active_check_in == "2026-11-10"
    assert session.active_check_out == "2026-11-14"
    assert session.active_guests == 2

    # Turn 2: User asks "Which is cheapest?"
    # Simulate available rooms returned
    session.last_available_rooms = [
        {"room_id": "bungalow-garden-301", "name": "Garden Tropical Bungalow", "nightly_rate": 290.0},
        {"room_id": "suite-deluxe-201", "name": "Deluxe Sunset Suite", "nightly_rate": 380.0}
    ]
    session.update_context_from_utterance("Which is cheapest?")
    # Context must be retained!
    assert session.active_check_in == "2026-11-10"
    assert session.active_check_out == "2026-11-14"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"

    # Turn 3: User says "Book that one"
    session.update_context_from_utterance("Book that one.")
    assert session.active_check_in == "2026-11-10"
    assert session.active_check_out == "2026-11-14"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"


# ==============================================================================
# Part 9: Regression Test for 3-Turn Cheapest Booking Flow
# ==============================================================================
@pytest.mark.asyncio
async def test_regression_three_turn_cheapest_booking_flow():
    """
    Exact 3-turn live voice booking flow regression test:
    Turn 1: "I need a room for two guests from October 17 to October 21."
    Turn 2: "Which one is the cheapest?"
    Turn 3: "Book the cheapest one."

    Verifies:
    - check_in remains 2026-10-17
    - check_out remains 2026-10-21
    - guests remains 2
    - selected room remains Garden Tropical Bungalow
    - booking proceeds without asking for dates again.
    """
    llm = GeminiLLMProvider()
    tools = tool_registry.get_tool_definitions()
    session = SessionState(call_sid="regr_3turn_flow_call", stream_sid="regr_3turn_flow_stream")

    # Turn 1: Caller states dates & guest count
    session.add_user_message("I need a room for two guests from October 17 to October 21.")
    assert session.active_check_in == "2026-10-17"
    assert session.active_check_out == "2026-10-21"
    assert session.active_guests == 2

    events1 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls1 = [e for e in events1 if e.get("type") == "tool_call"]
    assert len(tool_calls1) > 0
    assert tool_calls1[0]["name"] == "check_availability"
    assert tool_calls1[0]["arguments"]["check_in"] == "2026-10-17"
    assert tool_calls1[0]["arguments"]["check_out"] == "2026-10-21"

    avail_res = await tool_registry.execute_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"])
    session.update_context_from_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"], avail_res)
    session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res)})

    followup1 = [chunk async for chunk in llm.stream_chat(session.messages, tools=None)]
    text1 = "".join(c["content"] for c in followup1 if c.get("type") == "token")
    session.complete_assistant_turn(text1)
    assert len(text1) > 0

    # Turn 2: Caller asks for the cheapest option
    session.add_user_message("Which one is the cheapest?")
    assert session.active_check_in == "2026-10-17"
    assert session.active_check_out == "2026-10-21"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"

    events2 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    text2 = "".join(e["content"] for e in events2 if e.get("type") == "token")
    assert "garden tropical bungalow" in text2.lower() or "bungalow" in text2.lower()
    session.complete_assistant_turn(text2)

    # Turn 3: Caller requests booking the cheapest option
    session.add_user_message("Book the cheapest one.")
    # Context must strictly remain intact
    assert session.active_check_in == "2026-10-17"
    assert session.active_check_out == "2026-10-21"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"
    assert session.selected_room_name == "Garden Tropical Bungalow"

    events3 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls3 = [e for e in events3 if e.get("type") == "tool_call"]
    tokens3 = [e["content"] for e in events3 if e.get("type") == "token"]
    text3 = "".join(tokens3)

    # CRITICAL: Must NOT ask for dates again
    assert "what check-in and check-out dates" not in text3.lower()
    assert "what dates" not in text3.lower()

    # Must proceed directly with create_booking using established context
    assert len(tool_calls3) > 0
    assert tool_calls3[0]["name"] == "create_booking"
    assert tool_calls3[0]["arguments"]["room_id"] == "bungalow-garden-301"
    assert tool_calls3[0]["arguments"]["check_in"] == "2026-10-17"
    assert tool_calls3[0]["arguments"]["check_out"] == "2026-10-21"
    assert tool_calls3[0]["arguments"]["guests"] == 2


@pytest.mark.asyncio
async def test_user_changes_dates_in_later_turn():
    """
    Scenario G: User updates dates in a later turn.
    Turn 1: User says "I need a room from October 17 to October 21."
    Turn 2: User says "Actually, make it October 20 to October 25."
    Context and downstream tools must immediately use the new dates (2026-10-20 to 2026-10-25).
    """
    llm = GeminiLLMProvider()
    tools = tool_registry.get_tool_definitions()
    session = SessionState(call_sid="date_change_call", stream_sid="date_change_stream")

    # Turn 1: Initial dates
    session.add_user_message("I need a room from October 17 to October 21.")
    assert session.active_check_in == "2026-10-17"
    assert session.active_check_out == "2026-10-21"

    events1 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls1 = [e for e in events1 if e.get("type") == "tool_call"]
    assert len(tool_calls1) > 0
    assert tool_calls1[0]["arguments"]["check_in"] == "2026-10-17"
    assert tool_calls1[0]["arguments"]["check_out"] == "2026-10-21"
    avail_res1 = await tool_registry.execute_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"])
    session.update_context_from_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"], avail_res1)
    session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res1)})
    session.complete_assistant_turn("We have rooms available for October 17 to October 21.")

    # Turn 2: User changes dates
    session.add_user_message("Actually, make it October 20 to October 25.")
    # Stored dates MUST be updated!
    assert session.active_check_in == "2026-10-20"
    assert session.active_check_out == "2026-10-25"

    events2 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls2 = [e for e in events2 if e.get("type") == "tool_call"]
    assert len(tool_calls2) > 0
    assert tool_calls2[0]["name"] == "check_availability"
    assert tool_calls2[0]["arguments"]["check_in"] == "2026-10-20"
    assert tool_calls2[0]["arguments"]["check_out"] == "2026-10-25"


@pytest.mark.asyncio
async def test_regression_three_turn_november_booking_flow():
    """
    Requirement 18:
    Turn 1: "I need a room for two guests from November 20 to November 25."
    Turn 2: "Which one is the cheapest?"
    Turn 3: "Book that one."
    The booking MUST use: check_in = 2026-11-20, check_out = 2026-11-25, guests = 2.
    """
    llm = GeminiLLMProvider()
    tools = tool_registry.get_tool_definitions()
    session = SessionState(call_sid="regr_nov_call", stream_sid="regr_nov_stream")

    # Turn 1
    session.add_user_message("I need a room for two guests from November 20 to November 25.")
    assert session.active_check_in == "2026-11-20"
    assert session.active_check_out == "2026-11-25"
    assert session.active_guests == 2

    events1 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls1 = [e for e in events1 if e.get("type") == "tool_call"]
    assert len(tool_calls1) > 0
    assert tool_calls1[0]["arguments"]["check_in"] == "2026-11-20"
    assert tool_calls1[0]["arguments"]["check_out"] == "2026-11-25"
    avail_res = await tool_registry.execute_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"])
    session.update_context_from_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"], avail_res)
    session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res)})
    session.complete_assistant_turn("We have rooms available from November 20 to November 25.")

    # Turn 2: Which is cheapest?
    session.add_user_message("Which one is the cheapest?")
    assert session.active_check_in == "2026-11-20"
    assert session.active_check_out == "2026-11-25"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"

    events2 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    text2 = "".join(e["content"] for e in events2 if e.get("type") == "token")
    session.complete_assistant_turn(text2)

    # Turn 3: Book that one
    session.add_user_message("Book that one.")
    assert session.active_check_in == "2026-11-20"
    assert session.active_check_out == "2026-11-25"
    assert session.active_guests == 2
    assert session.selected_room == "bungalow-garden-301"

    events3 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls3 = [e for e in events3 if e.get("type") == "tool_call"]
    tokens3 = [e["content"] for e in events3 if e.get("type") == "token"]
    text3 = "".join(tokens3)

    assert "what check-in and check-out dates" not in text3.lower()
    assert "what dates" not in text3.lower()

    assert len(tool_calls3) > 0
    assert tool_calls3[0]["name"] == "create_booking"
    assert tool_calls3[0]["arguments"]["room_id"] == "bungalow-garden-301"
    assert tool_calls3[0]["arguments"]["check_in"] == "2026-11-20"
    assert tool_calls3[0]["arguments"]["check_out"] == "2026-11-25"
    assert tool_calls3[0]["arguments"]["guests"] == 2


@pytest.mark.asyncio
async def test_regression_three_turn_march_booking_flow():
    """
    Repeat 3-turn flow with completely different dates and guest count:
    Turn 1: "I need a room for four guests from March 10 to March 15 next year."
    Turn 2: "Which one is the cheapest?"
    Turn 3: "Book that one."
    The booking MUST use: check_in = 2027-03-10, check_out = 2027-03-15, guests = 4.
    """
    llm = GeminiLLMProvider()
    tools = tool_registry.get_tool_definitions()
    session = SessionState(call_sid="regr_mar_call", stream_sid="regr_mar_stream")

    # Turn 1
    session.add_user_message("I need a room for four guests from March 10 to March 15 next year.")
    assert session.active_check_in == "2027-03-10"
    assert session.active_check_out == "2027-03-15"
    assert session.active_guests == 4

    events1 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls1 = [e for e in events1 if e.get("type") == "tool_call"]
    assert len(tool_calls1) > 0
    assert tool_calls1[0]["arguments"]["check_in"] == "2027-03-10"
    assert tool_calls1[0]["arguments"]["check_out"] == "2027-03-15"
    assert tool_calls1[0]["arguments"]["guests"] == 4
    avail_res = await tool_registry.execute_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"])
    session.update_context_from_tool(tool_calls1[0]["name"], tool_calls1[0]["arguments"], avail_res)
    session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res)})
    session.complete_assistant_turn("We have 3 rooms available for 4 guests from March 10 to March 15.")

    # Turn 2: Which one is cheapest?
    # For 4 guests, available rooms: villa-ocean-101 ($650), suite-presidential-401 ($850), villa-family-501 ($520)
    # The cheapest is villa-family-501 ($520)
    session.add_user_message("Which one is the cheapest?")
    assert session.active_check_in == "2027-03-10"
    assert session.active_check_out == "2027-03-15"
    assert session.active_guests == 4
    assert session.selected_room == "villa-family-501"

    events2 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    text2 = "".join(e["content"] for e in events2 if e.get("type") == "token")
    session.complete_assistant_turn(text2)

    # Turn 3: Book that one
    session.add_user_message("Book that one.")
    assert session.active_check_in == "2027-03-10"
    assert session.active_check_out == "2027-03-15"
    assert session.active_guests == 4
    assert session.selected_room == "villa-family-501"

    events3 = [chunk async for chunk in llm.stream_chat(session.messages, tools=tools)]
    tool_calls3 = [e for e in events3 if e.get("type") == "tool_call"]
    tokens3 = [e["content"] for e in events3 if e.get("type") == "token"]
    text3 = "".join(tokens3)

    assert "what check-in and check-out dates" not in text3.lower()
    assert "what dates" not in text3.lower()

    assert len(tool_calls3) > 0
    assert tool_calls3[0]["name"] == "create_booking"
    assert tool_calls3[0]["arguments"]["room_id"] == "villa-family-501"
    assert tool_calls3[0]["arguments"]["check_in"] == "2027-03-10"
    assert tool_calls3[0]["arguments"]["check_out"] == "2027-03-15"
    assert tool_calls3[0]["arguments"]["guests"] == 4
