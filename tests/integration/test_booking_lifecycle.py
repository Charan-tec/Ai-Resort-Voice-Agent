import pytest
from app.tools.availability import check_availability
from app.tools.pricing import calculate_price
from app.tools.booking import create_booking, save_booking
from app.tools.email import send_confirmation_email


@pytest.mark.asyncio
async def test_complete_booking_lifecycle():
    """
    Validates the strict 5-stage lifecycle:
    check_availability -> calculate_price -> create_booking (HOLD) -> save_booking (CONFIRM) -> send_confirmation_email
    """
    # Stage 0: Clean up test date
    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM bookings WHERE check_in = '2026-12-10';")
        )
        await session.commit()

    # Stage 1: Availability
    avail = await check_availability(check_in="2026-12-10", check_out="2026-12-14", guests=2)
    assert avail["available"] is True
    room = avail["rooms"][0]
    room_id = room["room_id"]

    # Stage 2: Pricing
    pricing = await calculate_price(room_id=room_id, check_in="2026-12-10", check_out="2026-12-14", add_ons=["breakfast"])
    assert pricing["nights"] == 4
    total_price = pricing["total_price"]
    assert total_price > 0

    # Stage 3: Create Booking (Tentative Hold)
    hold = await create_booking(
        room_id=room_id,
        guest_name="Alexander Hamilton",
        guest_email="alexander@treasury.gov",
        guest_phone="+12125551789",
        check_in="2026-12-10",
        check_out="2026-12-14",
        total_price=total_price,
        guests=2,
        add_ons=["breakfast"]
    )
    assert hold["ok"] is True
    assert hold["status"] == "pending"
    assert "pending_token" in hold
    pending_token = hold["pending_token"]

    # Stage 4: Save Booking (Final Confirmation)
    confirm = await save_booking(pending_token=pending_token)
    assert confirm["ok"] is True
    assert confirm["status"] == "confirmed"
    assert "booking_id" in confirm
    booking_id = confirm["booking_id"]

    # Stage 5: Send Confirmation Email
    email_res = await send_confirmation_email(booking_id=booking_id, customer_email="alexander@treasury.gov")
    assert email_res["ok"] is True
    assert email_res["data"]["booking_id"] == booking_id
    assert email_res["data"]["delivery_status"] == "queued"
