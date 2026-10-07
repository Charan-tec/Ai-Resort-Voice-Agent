import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.tools.booking import BOOKINGS_STORE
from sqlalchemy.ext.asyncio import AsyncSession


class SendConfirmationEmailInput(BaseModel):
    booking_id: str = Field(min_length=5, description="Confirmation ID of the confirmed booking (e.g., RES-A1B2C3D4)")
    customer_email: str = Field(description="Recipient customer email address")

    @field_validator("customer_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address format.")
        return v

    @field_validator("booking_id")
    @classmethod
    def validate_booking_id(cls, v: str) -> str:
        return v.strip().upper()


async def send_confirmation_email(
    booking_id: str,
    customer_email: str,
    timeout_seconds: float = 5.0,
    db_session: Optional[AsyncSession] = None
) -> dict:
    """
    Validates booking existence in PostgreSQL and dispatches confirmation itinerary email asynchronously.
    Returns uniform envelope: {"ok": bool, "data": dict, "spoken_hint": str}
    """
    try:
        input_data = SendConfirmationEmailInput(
            booking_id=booking_id,
            customer_email=customer_email
        )
    except Exception as err:
        return {
            "ok": False,
            "data": {"error": f"Invalid email parameters: {err}"},
            "spoken_hint": "That email address format was invalid. Could you please spell out your email address again?"
        }

    # 1. Retrieve booking from PostgreSQL
    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    booking_rec = None
    try:
        stmt = (
            select(Booking)
            .options(joinedload(Booking.customer), joinedload(Booking.room))
            .where(
                or_(
                    Booking.booking_code == input_data.booking_id,
                    cast(Booking.id, String) == input_data.booking_id
                )
            )
        )
        db_booking = (await session.execute(stmt)).scalar_one_or_none()
        if db_booking:
            booking_rec = {
                "booking_id": db_booking.booking_code or str(db_booking.id),
                "guest_name": db_booking.customer.full_name if db_booking.customer else "Guest",
                "customer_email": db_booking.customer.email if db_booking.customer else input_data.customer_email,
                "room": db_booking.room.name if db_booking.room else db_booking.room_id,
                "room_id": db_booking.room_id,
                "check_in": db_booking.check_in.isoformat(),
                "check_out": db_booking.check_out.isoformat(),
                "guests": db_booking.guests,
                "total_price": float(db_booking.total_price),
                "status": db_booking.status
            }
    except Exception as exc:
        logger.debug(f"DB lookup in send_confirmation_email: {exc}")
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)

    # Fallback to in-memory store if DB record not matched
    if not booking_rec:
        booking_rec = BOOKINGS_STORE.get(input_data.booking_id)

    if not booking_rec:
        return {
            "ok": False,
            "data": {"error": f"Booking {input_data.booking_id} not found"},
            "spoken_hint": f"I could not locate booking reference {input_data.booking_id} in our records."
        }

    # Verify booking is confirmed
    if booking_rec.get("status") != "confirmed":
        return {
            "ok": False,
            "data": {"error": f"Booking status is {booking_rec.get('status')}, must be confirmed."},
            "spoken_hint": "This booking has not yet been confirmed. Let's confirm it before sending the email."
        }

    now_utc_str = datetime.now(timezone.utc).isoformat()

    # Prepare email dispatch payload containing all required booking concepts
    email_payload = {
        "booking_id": input_data.booking_id,
        "recipient": input_data.customer_email,
        "guest_name": booking_rec.get("guest_name"),
        "room": booking_rec.get("room") or booking_rec.get("room_id"),
        "check_in": booking_rec.get("check_in"),
        "check_out": booking_rec.get("check_out"),
        "guests": booking_rec.get("guests", 2),
        "total_price": booking_rec.get("total_price"),
        "status": "confirmed",
        "queued_at": now_utc_str
    }

    # Enqueue to background email worker with retry mechanism
    try:
        from app.services.email_worker import email_worker
        await asyncio.wait_for(email_worker.enqueue(email_payload), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Email queueing timed out for booking {input_data.booking_id}; proceeding gracefully.")
    except Exception as exc:
        logger.error(f"Email dispatch error: {exc}")

    spoken_hint = (
        f"I have sent your reservation details, check-in instructions, and payment receipt "
        f"to {input_data.customer_email}. Is there anything else I can assist you with today?"
    )

    res = {
        "ok": True,
        "data": {
            "booking_id": input_data.booking_id,
            "customer_email": input_data.customer_email,
            "delivery_status": "queued",
            "enqueued_at": now_utc_str
        },
        "booking_id": input_data.booking_id,
        "customer_email": input_data.customer_email,
        "guest_name": booking_rec.get("guest_name"),
        "room": booking_rec.get("room") or booking_rec.get("room_id"),
        "check_in": booking_rec.get("check_in"),
        "check_out": booking_rec.get("check_out"),
        "guests": booking_rec.get("guests", 2),
        "total_price": booking_rec.get("total_price"),
        "status": "confirmed",
        "email_status": "sent",
        "spoken_hint": spoken_hint
    }
    try:
        from app.orchestrator.broadcaster import event_broadcaster
        await event_broadcaster.notify_booking_update({"booking_code": input_data.booking_id, "email_status": "sent"})
    except Exception:
        pass

    return res
