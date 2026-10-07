import asyncio
from datetime import datetime, date, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Booking, Customer, Room, utcnow
from app.db.session import AsyncSessionLocal
from app.tools.availability import check_availability
from app.tools.booking import create_booking, save_booking
from app.tools.pricing import calculate_price
from app.tools.tool_registry import tool_registry, TOOLS_SCHEMAS


@pytest.mark.asyncio
async def test_public_tool_schemas_unmodified():
    """Verify that exactly the six public tools exist and db_session is not in their schemas."""
    schemas = tool_registry.get_tool_definitions()
    assert len(schemas) == 6

    expected_tool_names = {
        "check_availability",
        "calculate_price",
        "create_booking",
        "save_booking",
        "send_confirmation_email",
        "search_resort_knowledge"
    }
    actual_names = {s["function"]["name"] for s in schemas}
    assert actual_names == expected_tool_names

    for schema in schemas:
        fn = schema["function"]
        props = fn.get("parameters", {}).get("properties", {})
        # db_session must remain internal dependency and never exposed in function calling schemas
        assert "db_session" not in props, f"db_session leaked in tool schema: {fn['name']}"
        assert "db_session" not in fn.get("parameters", {}).get("required", [])


@pytest.mark.asyncio
async def test_check_availability_real_db_filtering():
    """Verify check_availability queries PostgreSQL and respects room type and capacity filters."""
    # Free dates in future
    check_in = "2027-05-01"
    check_out = "2027-05-05"

    # All rooms (guests=2)
    res_all = await check_availability(check_in=check_in, check_out=check_out, guests=2)
    assert res_all["available"] is True
    assert res_all["count"] >= 3

    # Room type filter: villa
    res_villa = await check_availability(check_in=check_in, check_out=check_out, room_type="villa", guests=2)
    assert res_villa["available"] is True
    assert all("villa" in r["room_type"].lower() for r in res_villa["rooms"])

    # High guest count: 4 guests (rooms with max_occupancy >= 4)
    res_large = await check_availability(check_in=check_in, check_out=check_out, guests=4)
    assert res_large["available"] is True
    assert all(r["max_occupancy"] >= 4 for r in res_large["rooms"])
    assert any(r["room_id"] == "villa-ocean-101" for r in res_large["rooms"])

    # Exceeding all capacities
    res_excess = await check_availability(check_in=check_in, check_out=check_out, guests=8)
    assert res_excess["available"] is False
    assert len(res_excess["rooms"]) == 0


@pytest.mark.asyncio
async def test_overlapping_and_non_overlapping_bookings():
    """Verify that overlapping pending and confirmed bookings block, but non-overlapping do not."""
    target_room = "suite-deluxe-201"
    b_start = "2027-06-10"
    b_end = "2027-06-15"

    # Clean up any leftover test booking for this specific test range
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM bookings WHERE room_id = '{target_room}' AND check_in = '{b_start}';")
        )
        await session.commit()

    # Initially free
    avail_before = await check_availability(check_in=b_start, check_out=b_end, room_type="suite", guests=2)
    assert any(r["room_id"] == target_room for r in avail_before["rooms"])

    # Create a hold (pending booking)
    hold = await create_booking(
        room_id=target_room,
        guest_name="Test Holder",
        guest_email="holder@test.com",
        guest_phone="+15550001111",
        check_in=b_start,
        check_out=b_end,
        total_price=1900.0,
        guests=2
    )
    assert hold["ok"] is True
    assert hold["status"] == "pending"

    # Overlapping check (should be excluded)
    avail_overlap = await check_availability(check_in="2027-06-12", check_out="2027-06-17", room_type="suite", guests=2)
    assert not any(r["room_id"] == target_room for r in avail_overlap["rooms"])

    # Non-overlapping check (2027-06-15 to 2027-06-20, half-open [check_in, check_out)) -> should be AVAILABLE
    avail_adjacent = await check_availability(check_in="2027-06-15", check_out="2027-06-20", room_type="suite", guests=2)
    assert any(r["room_id"] == target_room for r in avail_adjacent["rooms"])


@pytest.mark.asyncio
async def test_expired_hold_does_not_block_availability():
    """Verify that expired pending holds are transactionally transitioned and do not block availability."""
    target_room = "bungalow-garden-301"
    b_start = "2027-07-01"
    b_end = "2027-07-05"

    # Create an expired pending hold in the database
    async with AsyncSessionLocal() as session:
        expired_hold = Booking(
            id=uuid.uuid4(),
            booking_code=None,
            room_id=target_room,
            check_in=datetime.strptime(b_start, "%Y-%m-%d").date(),
            check_out=datetime.strptime(b_end, "%Y-%m-%d").date(),
            guests=2,
            status="pending",
            total_price=1160.0,
            pending_token=f"expired_{uuid.uuid4().hex[:8]}",
            hold_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=20)
        )
        session.add(expired_hold)
        await session.commit()

    # Query availability for that exact range
    avail = await check_availability(check_in=b_start, check_out=b_end, room_type="bungalow", guests=2)
    assert avail["available"] is True
    assert any(r["room_id"] == target_room for r in avail["rooms"])

    # Verify that the booking status in the DB was transitioned to 'expired'
    async with AsyncSessionLocal() as session:
        b_check = await session.get(Booking, expired_hold.id)
        assert b_check.status == "expired"


@pytest.mark.asyncio
async def test_concurrent_booking_exclusion_constraint():
    """Verify concurrent overlapping booking requests safely trigger the exclusion constraint."""
    target_room = "villa-ocean-101"
    c_in = "2027-08-01"
    c_out = "2027-08-05"

    # Ensure clean slate for test date range
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM bookings WHERE room_id = '{target_room}' AND check_in = '{c_in}';")
        )
        await session.commit()

    async def book_guest(name: str, email: str):
        return await create_booking(
            room_id=target_room,
            guest_name=name,
            guest_email=email,
            guest_phone="+15558889999",
            check_in=c_in,
            check_out=c_out,
            total_price=2600.0,
            guests=2
        )

    res_a, res_b = await asyncio.gather(
        book_guest("Guest One", "guest1@example.com"),
        book_guest("Guest Two", "guest2@example.com"),
        return_exceptions=True
    )

    results = [res_a, res_b]
    successes = [r for r in results if isinstance(r, dict) and r.get("ok") is True]
    conflicts = [r for r in results if isinstance(r, dict) and r.get("status") == "conflict"]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(conflicts) == 1, f"Expected 1 conflict, got {len(conflicts)}"
    assert "no longer available" in conflicts[0]["error"]
    assert "just reserved by another guest" in conflicts[0]["spoken_hint"]


@pytest.mark.asyncio
async def test_tool_registry_session_propagation_and_lifecycle():
    """Verify tool_registry correctly propagates db_session and manages lifecycle."""
    # When no session passed: tool_registry creates and cleans up session
    res = await tool_registry.execute_tool("check_availability", {
        "check_in": "2027-09-01",
        "check_out": "2027-09-05",
        "guests": 2
    })
    assert res["available"] is True

    # When session passed: tool_registry reuses it without closing
    async with AsyncSessionLocal() as outer_session:
        res2 = await tool_registry.execute_tool(
            "check_availability",
            {
                "check_in": "2027-09-01",
                "check_out": "2027-09-05",
                "guests": 2
            },
            db_session=outer_session
        )
        assert res2["available"] is True
        # Session is still active and open
        assert outer_session.is_active

    # Tool that does not accept session (e.g. search_resort_knowledge) does not get db_session
    res_rag = await tool_registry.execute_tool(
        "search_resort_knowledge",
        {"query": "spa treatments", "top_k": 1}
    )
    assert "results" in res_rag

