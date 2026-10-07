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
