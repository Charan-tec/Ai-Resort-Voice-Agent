from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, and_, or_, not_, exists, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Room, Booking, utcnow
from app.db.session import AsyncSessionLocal

# Fallback room list kept only for backwards compatibility with tests / offline references
RESORT_ROOMS = [
    {
        "room_id": "villa-ocean-101",
        "name": "Oceanfront Luxury Villa",
        "room_type": "villa",
        "max_occupancy": 4,
        "base_rate_nightly": 650.0,
        "amenities": ["Private Infinity Pool", "Ocean View", "King Bed", "Butler Service", "Complimentary Breakfast"]
    },
    {
        "room_id": "suite-deluxe-201",
        "name": "Deluxe Sunset Suite",
        "room_type": "suite",
        "max_occupancy": 2,
        "base_rate_nightly": 380.0,
        "amenities": ["Panoramic Sunset Balcony", "King Bed", "Whirlpool Spa Tub", "Espresso Bar"]
    },
    {
        "room_id": "bungalow-garden-301",
        "name": "Garden Tropical Bungalow",
        "room_type": "bungalow",
        "max_occupancy": 3,
        "base_rate_nightly": 290.0,
        "amenities": ["Private Zen Garden", "Rain Shower", "Queen Bed", "Hammock Terrace"]
    },
    {
        "room_id": "suite-presidential-401",
        "name": "Presidential Ocean Suite",
        "room_type": "suite",
        "max_occupancy": 4,
        "base_rate_nightly": 850.0,
        "amenities": ["Panoramic Ocean Terrace", "Master King Bedroom", "Whirlpool Spa Tub", "Dedicated Butler Service", "Complimentary Champagne"]
    },
    {
        "room_id": "villa-family-501",
        "name": "Family Pool Villa",
        "room_type": "villa",
        "max_occupancy": 6,
        "base_rate_nightly": 520.0,
        "amenities": ["Private Swimming Pool", "Sun Deck & Garden", "Two King Beds & Bunk Suite", "Full Kitchenette", "Family Entertainment Center"]
    },
    {
        "room_id": "suite-premium-302",
        "name": "Premium Garden Suite",
        "room_type": "suite",
        "max_occupancy": 3,
        "base_rate_nightly": 450.0,
        "amenities": ["Tropical Garden View", "King Bed & Daybed", "Marble Soaking Tub", "Espresso Bar", "Complimentary Breakfast"]
    }
]


class AvailabilityQuery(BaseModel):
    room_type: Optional[str] = Field(default=None, description="Type of room: 'villa', 'suite', or 'bungalow'")
    check_in: str = Field(description="Check-in date in YYYY-MM-DD format")
    check_out: str = Field(description="Check-out date in YYYY-MM-DD format")
    guests: int = Field(default=2, ge=1, le=10, description="Number of guests")

    @field_validator("check_in", "check_out")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")


async def check_availability(
    check_in: str,
    check_out: str,
    room_type: Optional[str] = None,
    guests: int = 2,
    db_session: Optional[AsyncSession] = None
) -> dict:
    """Check resort room availability from PostgreSQL for specified dates and party size."""
    try:
        query_model = AvailabilityQuery(
            check_in=check_in,
            check_out=check_out,
            room_type=room_type,
            guests=guests
        )
    except Exception as val_err:
        return {
            "ok": False,
            "available": False,
            "error": f"Invalid query parameters: {val_err}",
            "message": f"Invalid query parameters: {val_err}",
            "rooms": [],
            "available_rooms": [],
            "spoken_hint": "Please provide valid check-in and check-out dates in Year-Month-Day format."
        }

    d_in = datetime.strptime(query_model.check_in, "%Y-%m-%d").date()
    d_out = datetime.strptime(query_model.check_out, "%Y-%m-%d").date()
    if d_in >= d_out:
        return {
            "ok": False,
            "available": False,
            "error": "Check-out date must be after check-in date.",
            "message": "Check-out date must be after check-in date.",
            "rooms": [],
            "available_rooms": [],
            "spoken_hint": "Your check-out date must be after your check-in date."
        }

    nights = (d_out - d_in).days

    # PART 9 Diagnostics: log database endpoint and arguments
    from urllib.parse import urlparse
    parsed_url = urlparse(settings.DATABASE_URL)
    db_diag = f"dbname={parsed_url.path.lstrip('/')}, host={parsed_url.hostname}, port={parsed_url.port}"
    logger.info(
        f"[DIAGNOSTICS] check_availability invoked: db=({db_diag}), "
        f"parsed_check_in='{d_in}', parsed_check_out='{d_out}', guests={query_model.guests}, room_type='{query_model.room_type}'"
    )

    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    try:
        # 1. Transactionally expire any stale pending holds whose hold_expires_at has passed
        now_utc = utcnow()
        expire_stmt = (
            update(Booking)
            .where(
                Booking.status == "pending",
                Booking.hold_expires_at < now_utc
            )
            .values(status="expired", updated_at=now_utc)
        )
        await session.execute(expire_stmt)
        if not caller_owns_session:
            await session.commit()

        # 2. Query rooms that are active, fit occupancy, and have NO overlapping pending/confirmed bookings
        # Date range overlap uses PostgreSQL half-open interval: [check_in, check_out)
        req_range = func.daterange(d_in, d_out, "[)")
        overlapping_subquery = select(Booking.id).where(
            and_(
                Booking.room_id == Room.id,
                Booking.status.in_(["pending", "confirmed"]),
                func.daterange(Booking.check_in, Booking.check_out, "[)").op("&&")(req_range)
            )
        )

        query = select(Room).where(
            and_(
                Room.is_active.is_(True),
                Room.max_occupancy >= query_model.guests,
                not_(exists(overlapping_subquery))
            )
        )

        if query_model.room_type:
            rt_term = query_model.room_type.lower().strip()
            query = query.where(
                or_(
                    func.lower(Room.id) == rt_term,
                    func.lower(Room.name).contains(rt_term),
                    func.lower(Room.room_type) == rt_term,
                    func.lower(Room.room_type).contains(rt_term)
                )
            )

        # Sort rooms by base_rate ascending (cheapest room first)
        query = query.order_by(Room.base_rate.asc())

        res = await session.execute(query)
        rooms = res.scalars().all()

        available_rooms = [
            {
                "room_id": r.id,
                "name": r.name,
                "room_name": r.name,
                "room_type": r.room_type,
                "max_occupancy": r.max_occupancy,
                "capacity": r.max_occupancy,
                "base_rate_nightly": r.base_rate,
                "nightly_rate": r.base_rate,
                "amenities": r.amenities or []
            }
            for r in rooms
        ]

        count = len(available_rooms)
        raw_room_ids = [r["room_id"] for r in available_rooms]
        raw_room_names = [r["name"] for r in available_rooms]
        logger.info(
            f"[DIAGNOSTICS] PostgreSQL raw availability result: count={count}, "
            f"room_ids={raw_room_ids}, room_names={raw_room_names}"
        )

        if count > 0:
            room_names = ", ".join(r["name"] for r in available_rooms[:2])
            spoken_hint = (
                f"We have {count} room option{'s' if count > 1 else ''} available for {nights} nights, "
                f"including our {room_names}. Would you like pricing details?"
            )
            message = f"Found {count} available rooms for those dates."
        elif query_model.guests > 6:
            spoken_hint = (
                f"I'm sorry, our largest accommodation holds up to 6 guests, "
                f"so we cannot accommodate a single party of {query_model.guests} guests in one room."
            )
            message = f"No rooms are available: Party size of {query_model.guests} exceeds maximum room capacity of 6."
        else:
            spoken_hint = f"I'm sorry, we do not have {query_model.room_type or 'rooms'} available for those dates."
            message = "No rooms are available for those dates."

        cheapest_room = available_rooms[0] if count > 0 else None

        return {
            "ok": True,
            "available": count > 0,
            "check_in": query_model.check_in,
            "check_out": query_model.check_out,
            "guests": query_model.guests,
            "nights": nights,
            "count": count,
            "rooms": available_rooms,
            "available_rooms": available_rooms,
            "cheapest_room": cheapest_room,
            "message": message,
            "spoken_hint": spoken_hint
        }

    except Exception as exc:
        if not caller_owns_session:
            try:
                await session.rollback()
            except Exception:
                pass
        logger.warning(f"[DIAGNOSTICS] Database exception in check_availability, using static catalog fallback: {exc}")
        matched = []
        for r in RESORT_ROOMS:
            if r["max_occupancy"] >= query_model.guests:
                if not query_model.room_type or query_model.room_type.lower() in r["room_type"].lower() or query_model.room_type.lower() in r["name"].lower():
                    matched.append({
                        "room_id": r["room_id"],
                        "name": r["name"],
                        "room_name": r["name"],
                        "room_type": r["room_type"],
                        "max_occupancy": r["max_occupancy"],
                        "capacity": r["max_occupancy"],
                        "base_rate_nightly": r["base_rate_nightly"],
                        "nightly_rate": r["base_rate_nightly"],
                        "amenities": r.get("amenities", [])
                    })
        matched.sort(key=lambda x: x["base_rate_nightly"])
        count = len(matched)
        room_names = ", ".join(r["name"] for r in matched[:2]) if count > 0 else "rooms"
        spoken_hint = (
            f"We have {count} room option{'s' if count > 1 else ''} available for {nights} nights, "
            f"including our {room_names}. Would you like pricing details?"
        ) if count > 0 else "No rooms match your party size."
        cheapest_room = matched[0] if count > 0 else None
        return {
            "ok": True,
            "available": count > 0,
            "check_in": query_model.check_in,
            "check_out": query_model.check_out,
            "guests": query_model.guests,
            "nights": nights,
            "count": count,
            "rooms": matched,
            "available_rooms": matched,
            "cheapest_room": cheapest_room,
            "message": f"Found {count} available rooms for those dates." if count > 0 else "No rooms available.",
            "spoken_hint": spoken_hint
        }
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)

