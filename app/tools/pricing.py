from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Room
from app.db.session import AsyncSessionLocal
from app.tools.availability import RESORT_ROOMS

ADD_ON_PRICING = {
    "breakfast": 35.0,        # Per night
    "spa_credit": 150.0,      # Flat credit
    "airport_shuttle": 80.0,  # Flat round-trip
    "champagne": 95.0         # Bottle on arrival
}

TAX_RATE = 0.12        # 12% Resort & State tax
RESORT_FEE_NIGHT = 45.0  # $45 daily resort fee


class PricingQuery(BaseModel):
    room_id: str = Field(description="Unique ID of the selected room")
    check_in: str = Field(description="Check-in date in YYYY-MM-DD format")
    check_out: str = Field(description="Check-out date in YYYY-MM-DD format")
    booking_id: Optional[str] = Field(default=None, description="Optional booking reference code or confirmation number")
    add_ons: Optional[List[str]] = Field(default=None, description="Optional add-ons: breakfast, spa_credit, airport_shuttle, champagne")

    @field_validator("check_in", "check_out")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")


async def calculate_price(
    room_id: str,
    check_in: str,
    check_out: str,
    booking_id: Optional[str] = None,
    add_ons: Optional[List[str]] = None,
    db_session: Optional[AsyncSession] = None
) -> dict:
    """Calculate transparent price breakdown using PostgreSQL room rates, with fallback restricted to offline test mode."""
    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    try:
        # If booking_id is provided, retrieve authoritative booking details
        if booking_id:
            try:
                from app.tools.booking import get_booking_details
                b_info = await get_booking_details(booking_id, db_session=session)
                if b_info:
                    room_id = b_info.get("room_id") or room_id
                    check_in = b_info.get("check_in") or check_in
                    check_out = b_info.get("check_out") or check_out
                    if b_info.get("add_ons") and not add_ons:
                        add_ons = b_info["add_ons"]
            except Exception as b_err:
                logger.warning(f"calculate_price: could not retrieve booking details for '{booking_id}': {b_err}")

        query = PricingQuery(
            room_id=room_id,
            check_in=check_in,
            check_out=check_out,
            booking_id=booking_id,
            add_ons=add_ons
        )

        d_in = datetime.strptime(query.check_in, "%Y-%m-%d").date()
        d_out = datetime.strptime(query.check_out, "%Y-%m-%d").date()
        nights = (d_out - d_in).days
        if nights <= 0:
            return {
                "error": "Invalid date range: check-out must be after check-in.",
                "spoken_hint": "Please choose a check-out date after your check-in date."
            }

        logger.info(
            f"[DIAGNOSTICS] calculate_price invoked: room_id='{room_id}', "
            f"check_in='{check_in}', check_out='{check_out}', booking_id='{booking_id}', add_ons={add_ons}"
        )

        room_db = await session.get(Room, query.room_id)
        if not room_db:
            # Also try matching room by name or partial id
            from sqlalchemy import select, func
            stmt = select(Room).where(func.lower(Room.name) == query.room_id.strip().lower())
            room_db = (await session.execute(stmt)).scalar_one_or_none()

        if room_db:
            base_nightly = float(room_db.base_rate)
            room_name = room_db.name
            room_type = room_db.room_type if hasattr(room_db, "room_type") else (
                "bungalow" if "bungalow" in room_name.lower() else "suite" if "suite" in room_name.lower() else "villa"
            )
        elif settings.ENVIRONMENT in ("development", "test"):
            # Explicitly restricted offline test fallback
            fallback = next(
                (r for r in RESORT_ROOMS if r["room_id"].lower() == query.room_id.lower() or r["name"].lower() == query.room_id.lower()),
                RESORT_ROOMS[0]
            )
            logger.warning(f"calculate_price: Room '{query.room_id}' not found in database; using offline test fallback.")
            base_nightly = float(fallback["base_rate_nightly"])
            room_name = fallback["name"]
            room_type = fallback.get("room_type") or ("bungalow" if "bungalow" in room_name.lower() else "suite" if "suite" in room_name.lower() else "villa")
        else:
            return {
                "error": f"Room '{query.room_id}' not found in database.",
                "spoken_hint": "I could not locate that room in our system. Let me check what rooms are currently available."
            }
    except Exception as exc:
        if not caller_owns_session:
            await session.rollback()
        logger.error(f"[DIAGNOSTICS] Error querying room price from database: {exc}")
        if settings.ENVIRONMENT in ("development", "test"):
            fallback = next(
                (r for r in RESORT_ROOMS if r["room_id"].lower() == query.room_id.lower() or r["name"].lower() == query.room_id.lower()),
                RESORT_ROOMS[0]
            )
            base_nightly = float(fallback["base_rate_nightly"])
            room_name = fallback["name"]
            room_type = fallback.get("room_type") or ("bungalow" if "bungalow" in room_name.lower() else "suite" if "suite" in room_name.lower() else "villa")
        else:
            return {
                "error": "Database error while fetching pricing.",
                "spoken_hint": "I apologize, our pricing system is temporarily unavailable. Let me assist you shortly."
            }
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)

    room_subtotal = round(base_nightly * nights, 2)
    resort_fees = round(RESORT_FEE_NIGHT * nights, 2)
    taxes = round((room_subtotal + resort_fees) * TAX_RATE, 2)

    add_on_breakdown = {}
    add_ons_total = 0.0
    if query.add_ons:
        for item in query.add_ons:
            clean_item = item.strip().lower()
            if clean_item in ADD_ON_PRICING:
                cost = ADD_ON_PRICING[clean_item]
                if clean_item == "breakfast":
                    cost = cost * nights
                add_on_breakdown[clean_item] = cost
                add_ons_total += cost

    total_price = round(room_subtotal + resort_fees + taxes + add_ons_total, 2)

    add_ons_str = f", add-ons: ${add_ons_total:.2f}" if add_ons_total > 0 else ", add-ons: none"
    spoken_hint = (
        f"For your stay in the {room_name} ({room_type}) from {query.check_in} to {query.check_out} ({nights} nights): "
        f"The nightly rate is ${base_nightly:.2f}, lodging subtotal is ${room_subtotal:.2f}, "
        f"resort fee is ${resort_fees:.2f}, taxes are ${taxes:.2f}{add_ons_str}, "
        f"bringing the grand total to ${total_price:.2f} USD."
    )

    logger.info(
        f"[DIAGNOSTICS] calculate_price result: room='{room_name}', type='{room_type}', room_id='{query.room_id}', "
        f"dates='{query.check_in}' to '{query.check_out}', nights={nights}, nightly_rate={base_nightly}, subtotal={room_subtotal}, "
        f"resort_fees={resort_fees}, taxes={taxes}, total={total_price}"
    )

    return {
        "ok": True,
        "room": room_name,
        "room_name": room_name,
        "room_id": query.room_id,
        "room_type": room_type,
        "check_in": query.check_in,
        "check_out": query.check_out,
        "nights": nights,
        "number_of_nights": nights,
        "nightly_rate": base_nightly,
        "lodging_subtotal": room_subtotal,
        "subtotal": room_subtotal,
        "base_subtotal": room_subtotal,
        "resort_fee": resort_fees,
        "resort_fees": resort_fees,
        "taxes": taxes,
        "tax": taxes,
        "add_ons": add_on_breakdown,
        "add_ons_total": add_ons_total,
        "grand_total": total_price,
        "total": total_price,
        "total_price": total_price,
        "currency": "USD",
        "booking_id": booking_id,
        "confirmation_number": booking_id,
        "spoken_hint": spoken_hint
    }
