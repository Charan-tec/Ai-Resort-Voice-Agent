import pytest
from app.tools.tool_registry import tool_registry
from app.tools.availability import check_availability
from app.tools.pricing import calculate_price
from app.tools.booking import create_booking, save_booking
from app.tools.email import send_confirmation_email
from app.tools.retrieval import search_resort_knowledge


def test_registry_contains_exact_six_tools():
    defs = tool_registry.get_tool_definitions()
    assert len(defs) == 6
    names = {d["function"]["name"] for d in defs}
    expected = {
        "check_availability",
        "calculate_price",
        "create_booking",
        "save_booking",
        "send_confirmation_email",
        "search_resort_knowledge"
    }
    assert names == expected


@pytest.mark.asyncio
async def test_check_availability_tool():
    res = await check_availability(check_in="2026-10-01", check_out="2026-10-04", guests=2)
    assert res["ok"] is True
    assert res["available"] is True
    assert res["count"] > 0
    assert "available_rooms" in res
    assert "spoken_hint" in res


@pytest.mark.asyncio
async def test_check_availability_date_validation_rejects_reversed_dates():
    """Verify check_out <= check_in is rejected with clear error."""
    res = await check_availability(check_in="2026-10-14", check_out="2026-10-10", guests=2)
    assert res["ok"] is False
    assert res["available"] is False
    assert "error" in res
    assert "Check-out date must be after check-in date" in res["error"]


@pytest.mark.asyncio
async def test_check_availability_guest_validation():
    """Verify guests <= 0 is rejected by validation."""
    res = await check_availability(check_in="2026-10-10", check_out="2026-10-14", guests=0)
    assert res["ok"] is False
    assert res["available"] is False
    assert "error" in res


@pytest.mark.asyncio
async def test_check_availability_no_availability():
    """Verify exceeding party size returns empty available_rooms without error."""
    res = await check_availability(check_in="2026-10-10", check_out="2026-10-14", guests=10)
    assert res["ok"] is True
    assert res["available"] is False
    assert res["count"] == 0
    assert len(res["available_rooms"]) == 0
    assert "No rooms are available" in res["message"]


@pytest.mark.asyncio
async def test_calculate_price_tool():
    res = await calculate_price(
        room_id="villa-ocean-101",
        check_in="2026-10-01",
        check_out="2026-10-04",
        add_ons=["breakfast"]
    )
    assert res["nights"] == 3
    assert res["total_price"] > 0
    assert "add_ons_total" in res
    assert "spoken_hint" in res


@pytest.mark.asyncio
async def test_booking_lifecycle_hold_and_confirm(rollback_session):
    import uuid
    from app.db.models import Room

    # Seed an isolated, unique test room strictly within this rollback transaction
    unique_room_id = f"test-room-{uuid.uuid4().hex[:8]}"
    test_room = Room(
        id=unique_room_id,
        name="Isolated Unit Test Villa",
        room_type="villa",
        max_occupancy=4,
        base_rate=500.0,
        is_active=True,
        amenities=["Private Infinity Pool", "Ocean View"]
    )
    rollback_session.add(test_room)
    await rollback_session.flush()

    # 1. Create booking (Hold stage) using isolated transaction session
    hold_res = await create_booking(
        room_id=unique_room_id,
        guest_name="Jane Doe",
        guest_email="jane.doe@example.com",
        guest_phone="+15551234567",
        check_in="2026-11-10",
        check_out="2026-11-14",
        total_price=2150.0,
        guests=2,
        db_session=rollback_session
    )
    assert hold_res["ok"] is True
    assert hold_res["status"] == "pending"
    assert "pending_token" in hold_res
    pending_token = hold_res["pending_token"]

    # 2. Save booking (Confirm stage)
    confirm_res = await save_booking(pending_token=pending_token, db_session=rollback_session)
    assert confirm_res["ok"] is True
    assert confirm_res["status"] == "confirmed"
    assert "booking_id" in confirm_res
    booking_id = confirm_res["booking_id"]

    # 3. Idempotency test: calling save_booking again with the same token returns confirmed
    repeat_res = await save_booking(pending_token=pending_token, db_session=rollback_session)
    assert repeat_res["ok"] is True
    assert repeat_res["booking_id"] == booking_id

    # 4. Send confirmation email (Uniform envelope)
    email_res = await send_confirmation_email(booking_id=booking_id, customer_email="jane.doe@example.com")
    assert email_res["ok"] is True
    assert "data" in email_res
    assert "spoken_hint" in email_res
    assert email_res["data"]["booking_id"] == booking_id


@pytest.mark.asyncio
async def test_search_resort_knowledge_tool():
    res = await search_resort_knowledge(query="What are the pool hours?", top_k=2)
    assert "query" in res
    assert "results" in res
    assert "spoken_hint" in res


@pytest.mark.asyncio
async def test_regression_booking_confirmation_turn_flow(rollback_session):
    """
    Regression Test (Requirement 12):
    create_booking() -> user says 'yeah confirm' -> save_booking() -> pending becomes confirmed.
    Verifies that pending_token and booking_id are preserved separately and
    save_booking() successfully matches and confirms the booking in PostgreSQL.
    """
    import uuid
    from sqlalchemy import select
    from app.db.models import Booking, Room
    from app.orchestrator.session import SessionState

    # 1. Seed an isolated test room
    unique_room_id = f"test-regr1-{uuid.uuid4().hex[:8]}"
    test_room = Room(
        id=unique_room_id,
        name="Regression Test Suite",
        room_type="suite",
        max_occupancy=3,
        base_rate=450.0,
        is_active=True,
        amenities=["Ocean View", "Balcony"]
    )
    rollback_session.add(test_room)
    await rollback_session.flush()

    # 2. create_booking() -> creates pending hold
    hold_res = await create_booking(
        room_id=unique_room_id,
        guest_name="Sarah Connor",
        guest_email="sarah@example.com",
        guest_phone="+15551234567",
        check_in="2026-11-15",
        check_out="2026-11-18",
        total_price=1350.0,
        guests=2,
        db_session=rollback_session
    )
    assert hold_res["ok"] is True
    assert hold_res["status"] == "pending"
    assert "pending_token" in hold_res
    assert "booking_id" in hold_res
    pending_token = hold_res["pending_token"]
    booking_uuid = hold_res["booking_id"]

    # 3. Update session state with tool result
    session = SessionState("call_regr_1", "stream_regr_1")
    session.update_context_from_tool("create_booking", {}, hold_res)
    assert session.active_pending_token == pending_token
    assert session.active_booking_id == booking_uuid

    # 4. User says "yeah confirm"
    session.add_user_message("yeah confirm")
    assert session.current_intent == "confirmation"

    # 5. Orchestrator parameter injection:
    # active_pending_token only into pending_token, active_booking_id only into booking_id
    arguments = {}
    if not arguments.get("pending_token") and session.active_pending_token:
        arguments["pending_token"] = session.active_pending_token
    if not arguments.get("booking_id") and getattr(session, "active_booking_id", None):
        arguments["booking_id"] = session.active_booking_id

    assert arguments["pending_token"] == pending_token
    assert arguments["booking_id"] == booking_uuid

    # 6. save_booking() executes with both arguments preserved
    confirm_res = await save_booking(
        pending_token=arguments["pending_token"],
        booking_id=arguments["booking_id"],
        db_session=rollback_session
    )
    assert confirm_res["ok"] is True
    assert confirm_res["status"] == "confirmed"
    assert "booking_code" in confirm_res
    assert confirm_res["booking_code"].startswith("RES-")
    confirmed_code = confirm_res["booking_code"]

    # 7. Verify in PostgreSQL that pending hold transitioned to confirmed
    stmt = select(Booking).where(Booking.id == uuid.UUID(booking_uuid))
    booking_in_db = (await rollback_session.execute(stmt)).scalar_one_or_none()
    assert booking_in_db is not None
    assert booking_in_db.status == "confirmed"
    assert booking_in_db.booking_code == confirmed_code
    assert booking_in_db.pending_token == pending_token


@pytest.mark.asyncio
async def test_regression_booking_confirmation_repeat_idempotency_no_duplicates(rollback_session):
    """
    Regression Test (Requirement 13):
    successful confirmation -> user says 'yeah confirm' again -> no duplicate booking is created.
    """
    import uuid
    from sqlalchemy import select
    from app.db.models import Booking, Room
    from app.orchestrator.session import SessionState

    # 1. Seed an isolated test room
    unique_room_id = f"test-regr2-{uuid.uuid4().hex[:8]}"
    test_room = Room(
        id=unique_room_id,
        name="Regression Idempotency Villa",
        room_type="villa",
        max_occupancy=4,
        base_rate=650.0,
        is_active=True,
        amenities=["Private Pool", "Beach Access"]
    )
    rollback_session.add(test_room)
    await rollback_session.flush()

    # 2. create_booking() -> pending hold
    hold_res = await create_booking(
        room_id=unique_room_id,
        guest_name="John Connor",
        guest_email="john@example.com",
        guest_phone="+15559876543",
        check_in="2026-11-20",
        check_out="2026-11-24",
        total_price=2600.0,
        guests=2,
        db_session=rollback_session
    )
    assert hold_res["ok"] is True
    assert hold_res["status"] == "pending"
    pending_token = hold_res["pending_token"]
    booking_uuid = hold_res["booking_id"]

    # 3. First confirmation: user says "yeah confirm" -> confirmed
    session = SessionState("call_regr_2", "stream_regr_2")
    session.update_context_from_tool("create_booking", {}, hold_res)
    session.add_user_message("yeah confirm")

    first_args = {}
    if not first_args.get("pending_token") and session.active_pending_token:
        first_args["pending_token"] = session.active_pending_token
    if not first_args.get("booking_id") and getattr(session, "active_booking_id", None):
        first_args["booking_id"] = session.active_booking_id

    confirm_res = await save_booking(
        pending_token=first_args["pending_token"],
        booking_id=first_args["booking_id"],
        db_session=rollback_session
    )
    assert confirm_res["ok"] is True
    assert confirm_res["status"] == "confirmed"
    confirmed_code = confirm_res["booking_code"]

    # Session receives confirmation results
    session.update_context_from_tool("save_booking", first_args, confirm_res)
    assert session.confirmed_booking_id == confirmed_code
    assert session.active_booking_id == confirmed_code

    # 4. Repeat: user says "yeah confirm" again
    session.add_user_message("yeah confirm")

    second_args = {}
    if not second_args.get("pending_token") and session.active_pending_token:
        second_args["pending_token"] = session.active_pending_token
    if not second_args.get("booking_id") and getattr(session, "active_booking_id", None):
        second_args["booking_id"] = session.active_booking_id

    repeat_res = await save_booking(
        pending_token=second_args.get("pending_token"),
        booking_id=second_args.get("booking_id"),
        db_session=rollback_session
    )
    assert repeat_res["ok"] is True
    assert repeat_res["status"] == "confirmed"
    assert repeat_res["booking_code"] == confirmed_code

    # 5. Verify PostgreSQL constraint and row count: exactly 1 booking exists, zero duplicates
    stmt = select(Booking).where(Booking.room_id == unique_room_id)
    all_bookings = (await rollback_session.execute(stmt)).scalars().all()
    assert len(all_bookings) == 1
    assert all_bookings[0].id == uuid.UUID(booking_uuid)
    assert all_bookings[0].booking_code == confirmed_code
    assert all_bookings[0].status == "confirmed"

