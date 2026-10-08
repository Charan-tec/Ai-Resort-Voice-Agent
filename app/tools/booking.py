from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.db.models import Booking, Customer, Room, utcnow
from app.db.session import AsyncSessionLocal

# Store for active holds and confirmed bookings (in-memory mirrored for backwards compatibility)
BOOKINGS_STORE: Dict[str, dict] = {}       # booking_id -> booking record
HOLD_TOKENS_STORE: Dict[str, dict] = {}    # pending_token -> hold record


class CreateBookingInput(BaseModel):
    room_id: str = Field(description="Room ID to book")
    guest_name: str = Field(default="Valued Guest", min_length=2, description="Full name of guest")
    guest_email: str = Field(default="guest@azureparadise-resort.com", description="Valid email address for reservation")
    guest_phone: str = Field(default="+1-808-555-0100", min_length=7, description="Contact telephone number")
    check_in: str = Field(description="Check-in date (YYYY-MM-DD)")
    check_out: str = Field(description="Check-out date (YYYY-MM-DD)")
    guests: int = Field(default=2, ge=1, le=10)
    total_price: float = Field(gt=0, description="Agreed total price in USD")
    currency: Optional[str] = Field(default="USD", description="Currency code for booking (e.g. USD, EUR, INR)")
    add_ons: Optional[List[str]] = Field(default=None)

    @field_validator("guest_email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address format.")
        return v.strip().lower()

    @field_validator("check_in", "check_out")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format.")


class SaveBookingInput(BaseModel):
    pending_token: Optional[str] = Field(default=None, description="The pending hold token issued by create_booking")
    booking_id: Optional[str] = Field(default=None, description="The booking ID, confirmation code, or reservation UUID")


async def create_booking(
    room_id: str,
    guest_name: Optional[str] = "Valued Guest",
    guest_email: Optional[str] = "guest@azureparadise-resort.com",
    guest_phone: Optional[str] = "+1-808-555-0100",
    check_in: str = "",
    check_out: str = "",
    total_price: Optional[float] = None,
    guests: int = 2,
    currency: Optional[str] = "USD",
    add_ons: Optional[List[str]] = None,
    db_session: Optional[AsyncSession] = None
) -> dict:
    """
    Stage 1 of booking: Places a 15-minute tentative hold in PostgreSQL and returns a pending_token.
    Protected by the btree_gist exclusion constraint on overlapping [check_in, check_out) dates.
    """
    effective_name = guest_name.strip() if (guest_name and guest_name.strip()) else "Valued Guest"
    effective_email = guest_email.strip() if (guest_email and "@" in guest_email) else "guest@azureparadise-resort.com"
    effective_phone = guest_phone.strip() if (guest_phone and len(guest_phone.strip()) >= 7) else "+1-808-555-0100"

    effective_price = float(total_price) if (total_price and float(total_price) > 0) else None
    if effective_price is None:
        room_rates = {
            "bungalow-garden-301": 290.0,
            "suite-deluxe-201": 380.0,
            "suite-premium-302": 450.0,
            "villa-family-501": 520.0,
            "villa-ocean-101": 650.0,
            "suite-presidential-401": 850.0,
        }
        rate = room_rates.get(room_id, 380.0)
        try:
            n = max(1, (datetime.strptime(check_out, "%Y-%m-%d").date() - datetime.strptime(check_in, "%Y-%m-%d").date()).days)
        except Exception:
            n = 3
        sub = rate * n
        fees = 45.0 * n
        tax = (sub + fees) * 0.12
        effective_price = round(sub + fees + tax, 2)

    try:
        input_data = CreateBookingInput(
            room_id=room_id,
            guest_name=effective_name,
            guest_email=effective_email,
            guest_phone=effective_phone,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            total_price=effective_price,
            currency=currency or "USD",
            add_ons=add_ons
        )
    except Exception as val_err:
        return {
            "ok": False,
            "status": "error",
            "error": f"Invalid booking input: {val_err}",
            "spoken_hint": "I encountered an issue with the booking details provided. Please verify the dates and contact info."
        }

    d_in = datetime.strptime(input_data.check_in, "%Y-%m-%d").date()
    d_out = datetime.strptime(input_data.check_out, "%Y-%m-%d").date()
    if d_in >= d_out:
        return {
            "ok": False,
            "status": "error",
            "error": "Check-out date must be after check-in date.",
            "spoken_hint": "Your check-out date must be after your check-in date."
        }

    logger.info(
        f"[DIAGNOSTICS] create_booking arguments: room_id='{input_data.room_id}', guest_name='{input_data.guest_name}', "
        f"guest_email='{input_data.guest_email}', check_in='{input_data.check_in}', check_out='{input_data.check_out}', "
        f"total_price={input_data.total_price}, guests={input_data.guests}"
    )

    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    try:
        # 1. Transactionally expire any stale pending holds before checking conflict
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

        # 2. Verify room exists (by ID or name)
        from sqlalchemy import and_, func
        room = await session.get(Room, input_data.room_id)
        if not room:
            name_stmt = select(Room).where(func.lower(Room.name) == input_data.room_id.strip().lower())
            room = (await session.execute(name_stmt)).scalar_one_or_none()
            if room:
                input_data.room_id = room.id

        if not room:
            return {
                "ok": False,
                "status": "error",
                "error": f"Room '{input_data.room_id}' not found.",
                "spoken_hint": "I could not locate that room in our system."
            }

        # 2b. Re-check availability immediately before creating reservation
        req_range = func.daterange(d_in, d_out, "[)")
        overlap_check = select(Booking.id).where(
            and_(
                Booking.room_id == input_data.room_id,
                Booking.status.in_(["pending", "confirmed"]),
                func.daterange(Booking.check_in, Booking.check_out, "[)").op("&&")(req_range)
            )
        )
        existing_conflict = (await session.execute(overlap_check)).first()
        if existing_conflict:
            return {
                "ok": False,
                "status": "conflict",
                "error": "The selected room is no longer available for those dates.",
                "message": "The selected room is no longer available for those dates.",
                "spoken_hint": "I'm sorry, that room was just reserved by another guest for those dates. Let me find another available option for you."
            }

        # 3. Retrieve or create Customer
        cust_stmt = select(Customer).where(Customer.email == input_data.guest_email)
        customer = (await session.execute(cust_stmt)).scalar_one_or_none()
        if not customer:
            customer = Customer(
                id=uuid.uuid4(),
                full_name=input_data.guest_name,
                email=input_data.guest_email,
                phone=input_data.guest_phone,
                created_at=now_utc
            )
            session.add(customer)
            await session.flush()

        # 4. Insert pending Booking record
        pending_token = f"hold_{secrets.token_urlsafe(16)}"
        expires_at = now_utc + timedelta(minutes=15)

        booking = Booking(
            id=uuid.uuid4(),
            booking_code=None,
            room_id=input_data.room_id,
            customer_id=customer.id,
            check_in=d_in,
            check_out=d_out,
            guests=input_data.guests,
            status="pending",
            total_price=input_data.total_price,
            currency=input_data.currency or "USD",
            pending_token=pending_token,
            hold_expires_at=expires_at,
            add_ons=input_data.add_ons or [],
            created_at=now_utc,
            updated_at=now_utc
        )
        session.add(booking)
        if not caller_owns_session:
            await session.commit()
        else:
            await session.flush()

        # Mirrored memory record for backwards compatibility
        r_type_val = room.room_type if (room and hasattr(room, "room_type")) else ("bungalow" if "bungalow" in input_data.room_id else "suite" if "suite" in input_data.room_id else "villa")
        hold_record = {
            "pending_token": pending_token,
            "status": "pending",
            "room_id": input_data.room_id,
            "room_name": room.name if room else input_data.room_id,
            "room_type": r_type_val,
            "guest_name": input_data.guest_name,
            "guest_email": input_data.guest_email,
            "guest_phone": input_data.guest_phone,
            "check_in": input_data.check_in,
            "check_out": input_data.check_out,
            "guests": input_data.guests,
            "total_price": input_data.total_price,
            "currency": input_data.currency or "USD",
            "add_ons": input_data.add_ons or [],
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
            "booking_id": str(booking.id)
        }
        HOLD_TOKENS_STORE[pending_token] = hold_record
        logger.info(
            f"[DIAGNOSTICS] create_booking result: booking_id={booking.id}, "
            f"room_id='{input_data.room_id}', pending_token='{pending_token}', status='pending'"
        )

        spoken_hint = (
            f"I have placed a 15-minute courtesy hold on the reservation for {input_data.guest_name} "
            f"from {input_data.check_in} to {input_data.check_out}. The total is ${input_data.total_price:.2f}. "
            f"Shall I go ahead and confirm this booking for you now?"
        )

        r_type = room.room_type if (room and hasattr(room, "room_type")) else ("bungalow" if "bungalow" in input_data.room_id else "suite" if "suite" in input_data.room_id else "villa")
        res = {
            "ok": True,
            "status": "pending",
            "booking_id": str(booking.id),
            "reservation_id": str(booking.id),
            "pending_token": pending_token,
            "room_id": input_data.room_id,
            "room_name": room.name if room else input_data.room_id,
            "room_type": r_type,
            "guest_name": input_data.guest_name,
            "guest_email": input_data.guest_email,
            "guest_phone": input_data.guest_phone,
            "check_in": input_data.check_in,
            "check_out": input_data.check_out,
            "guests": input_data.guests,
            "total_price": input_data.total_price,
            "grand_total": input_data.total_price,
            "currency": input_data.currency or "USD",
            "expires_at": expires_at.isoformat(),
            "spoken_hint": spoken_hint
        }
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            await event_broadcaster.notify_booking_update(res)
        except Exception:
            pass

        return res

    except IntegrityError as exc:
        if not caller_owns_session:
            await session.rollback()
        err_msg = str(exc).lower()
        if "exclusion" in err_msg or "no_overlapping_bookings" in err_msg or "23p01" in err_msg:
            logger.warning(f"[DIAGNOSTICS] Exclusion constraint prevented overlapping hold for room {input_data.room_id}: {exc}")
            return {
                "ok": False,
                "status": "conflict",
                "error": "The selected room is no longer available for those dates.",
                "message": "The selected room is no longer available for those dates.",
                "spoken_hint": "I'm sorry, that room was just reserved by another guest for those dates. Let me find another available option for you."
            }
        logger.error(f"[DIAGNOSTICS] Database integrity error in create_booking: {exc}")
        return {
            "ok": False,
            "status": "error",
            "error": "A reservation data error occurred.",
            "spoken_hint": "I encountered an error placing that hold. Please let me try again."
        }
    except Exception as exc:
        if not caller_owns_session:
            try:
                await session.rollback()
            except Exception:
                pass
        logger.warning(f"[DIAGNOSTICS] Database unavailable in create_booking, utilizing memory hold store: {exc}")
        pending_token = f"hold_{secrets.token_urlsafe(16)}"
        expires_at = now_utc + timedelta(minutes=15)
        hold_record = {
            "pending_token": pending_token,
            "status": "pending",
            "room_id": input_data.room_id,
            "guest_name": input_data.guest_name,
            "guest_email": input_data.guest_email,
            "guest_phone": input_data.guest_phone,
            "check_in": input_data.check_in,
            "check_out": input_data.check_out,
            "guests": input_data.guests,
            "total_price": input_data.total_price,
            "currency": input_data.currency or "USD",
            "add_ons": input_data.add_ons or [],
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
            "booking_id": None
        }
        HOLD_TOKENS_STORE[pending_token] = hold_record
        res = {
            "ok": True,
            "status": "pending",
            "booking_id": pending_token,
            "reservation_id": pending_token,
            "pending_token": pending_token,
            "room_id": input_data.room_id,
            "guest_name": input_data.guest_name,
            "guest_email": input_data.guest_email,
            "check_in": input_data.check_in,
            "check_out": input_data.check_out,
            "guests": input_data.guests,
            "total_price": input_data.total_price,
            "grand_total": input_data.total_price,
            "currency": input_data.currency or "USD",
            "expires_at": expires_at.isoformat(),
            "spoken_hint": (
                f"I have placed a 15-minute courtesy hold on the reservation for {input_data.guest_name} "
                f"from {input_data.check_in} to {input_data.check_out}. The total is ${input_data.total_price:.2f}. "
                f"Shall I go ahead and confirm this booking for you now?"
            )
        }
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            await event_broadcaster.notify_booking_update(res)
        except Exception:
            pass
        return res
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)


async def save_booking(
    pending_token: Optional[str] = None,
    booking_id: Optional[str] = None,
    db_session: Optional[AsyncSession] = None
) -> dict:
    """
    Stage 2 of booking: Confirms a pending hold into an official reservation in PostgreSQL.
    Accepts pending_token, booking_id, or confirmation code.
    Idempotent: repeating save_booking with the same identifier returns existing confirmed booking.
    """
    logger.info(f"[DIAGNOSTICS] save_booking arguments: pending_token='{pending_token}', booking_id='{booking_id}'")
    raw_token = (pending_token or "").strip() if pending_token else ""
    raw_id = (booking_id or "").strip() if booking_id else ""

    if not raw_token and not raw_id:
        return {
            "ok": False,
            "status": "error",
            "error": "Missing booking identifier: pending_token or booking_id is required.",
            "spoken_hint": "I could not locate an active hold for this reservation. Let's re-check availability."
        }

    try:
        input_data = SaveBookingInput(pending_token=raw_token or None, booking_id=raw_id or None)
    except Exception as val_err:
        return {
            "ok": False,
            "status": "error",
            "error": f"Invalid token or booking_id: {val_err}",
            "spoken_hint": "I could not locate an active hold for this reservation. Let's re-check availability."
        }

    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    try:
        from sqlalchemy import or_

        # Prepare lookup conditions for booking_id if provided
        id_conditions = []
        if raw_id:
            id_conditions.append(Booking.booking_code == raw_id)
            try:
                val_uuid = uuid.UUID(raw_id)
                id_conditions.append(Booking.id == val_uuid)
            except Exception:
                pass

        booking = None
        if raw_token and raw_id:
            # Both provided: query each separately to verify they refer to the exact same booking
            booking_by_token = (await session.execute(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.room))
                .where(Booking.pending_token == raw_token)
            )).scalar_one_or_none()

            booking_by_id = (await session.execute(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.room))
                .where(or_(*id_conditions))
            )).scalar_one_or_none()

            if booking_by_token and booking_by_id:
                if booking_by_token.id != booking_by_id.id:
                    return {
                        "ok": False,
                        "status": "error",
                        "error": "Mismatch: pending_token and booking_id refer to different bookings.",
                        "spoken_hint": "I found conflicting reservation details. Let's re-check availability."
                    }
                booking = booking_by_token
            elif booking_by_token or booking_by_id:
                return {
                    "ok": False,
                    "status": "error",
                    "error": "Mismatch: pending_token and booking_id do not refer to the same booking.",
                    "spoken_hint": "I found conflicting reservation details. Let's re-check availability."
                }
            else:
                booking = None

        elif raw_token:
            booking = (await session.execute(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.room))
                .where(Booking.pending_token == raw_token)
            )).scalar_one_or_none()

        elif raw_id:
            booking = (await session.execute(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.room))
                .where(or_(*id_conditions))
            )).scalar_one_or_none()

        if not booking:
            # Memory store fallback (for offline or uncommitted holds)
            matched_hold = None
            if raw_token and raw_id:
                hold_by_tok = HOLD_TOKENS_STORE.get(raw_token)
                hold_by_id = None
                for h_tok, h_data in HOLD_TOKENS_STORE.items():
                    if h_data.get("booking_id") == raw_id or h_data.get("booking_code") == raw_id or h_tok == raw_id:
                        hold_by_id = h_data
                        break
                if hold_by_tok and hold_by_id:
                    if hold_by_tok != hold_by_id:
                        return {
                            "ok": False,
                            "status": "error",
                            "error": "Mismatch: pending_token and booking_id refer to different holds.",
                            "spoken_hint": "I found conflicting reservation details. Let's re-check availability."
                        }
                    matched_hold = hold_by_tok
                elif hold_by_tok or hold_by_id:
                    return {
                        "ok": False,
                        "status": "error",
                        "error": "Mismatch: pending_token and booking_id do not refer to the same hold.",
                        "spoken_hint": "I found conflicting reservation details. Let's re-check availability."
                    }
            elif raw_token:
                matched_hold = HOLD_TOKENS_STORE.get(raw_token)
            elif raw_id:
                for h_tok, h_data in HOLD_TOKENS_STORE.items():
                    if h_data.get("booking_id") == raw_id or h_data.get("booking_code") == raw_id or h_tok == raw_id:
                        matched_hold = h_data
                        break

            if matched_hold:
                hold = matched_hold
                b_code = hold.get("booking_code") or hold.get("booking_id")
                is_already_conf = hold.get("status") == "confirmed" and b_code and str(b_code).startswith("RES-")
                final_booking_id = b_code if is_already_conf else f"RES-{uuid.uuid4().hex[:8].upper()}"
                r_id = hold.get("room_id", "")
                r_name = hold.get("room_name") or r_id
                r_type = hold.get("room_type") or ("bungalow" if "bungalow" in r_id else "suite" if "suite" in r_id else "villa")
                g_name = hold.get("guest_name", "Valued Guest")
                g_email = hold.get("guest_email", "")
                t_price = float(hold.get("total_price", 0.0))
                c_in = hold.get("check_in", "")
                c_out = hold.get("check_out", "")
                g_cnt = hold.get("guests", 2)
                now_str = utcnow().isoformat()

                hold["status"] = "confirmed"
                hold["booking_id"] = final_booking_id
                hold["booking_code"] = final_booking_id

                BOOKINGS_STORE[final_booking_id] = {
                    "booking_id": final_booking_id,
                    "booking_code": final_booking_id,
                    "confirmation_number": final_booking_id,
                    "guest_name": g_name,
                    "guest_email": g_email,
                    "room_id": r_id,
                    "room_name": r_name,
                    "room_type": r_type,
                    "check_in": c_in,
                    "check_out": c_out,
                    "guests": g_cnt,
                    "total_price": t_price,
                    "grand_total": t_price,
                    "currency": hold.get("currency", "USD"),
                    "status": "confirmed",
                    "created_at": now_str
                }
                spoken_hint = (
                    f"Your booking {final_booking_id} is already confirmed for {g_name}."
                    if is_already_conf else
                    f"Wonderful! Your reservation is officially confirmed! Your confirmation number is {final_booking_id}. "
                    f"I can email your itinerary and receipt now. Would you like me to send that to {g_email}?"
                )
                return {
                    "ok": True,
                    "status": "confirmed",
                    "booking_id": final_booking_id,
                    "booking_code": final_booking_id,
                    "confirmation_number": final_booking_id,
                    "reservation_id": final_booking_id,
                    "guest_name": g_name,
                    "guest_email": g_email,
                    "room_id": r_id,
                    "room_name": r_name,
                    "room_type": r_type,
                    "check_in": c_in,
                    "check_out": c_out,
                    "guests": g_cnt,
                    "total_price": t_price,
                    "grand_total": t_price,
                    "currency": hold.get("currency", "USD"),
                    "created_at": now_str,
                    "spoken_hint": spoken_hint
                }

            desc = f"token '{raw_token}' and id '{raw_id}'" if (raw_token and raw_id) else f"'{raw_token or raw_id}'"
            return {
                "ok": False,
                "status": "error",
                "error": f"Hold token not found or expired: {desc}",
                "spoken_hint": "I could not locate an active hold for this reservation. Let's re-check availability."
            }

        room_name = booking.room.name if booking.room else booking.room_id
        room_type = booking.room.room_type if (booking.room and hasattr(booking.room, "room_type")) else (
            "bungalow" if "bungalow" in booking.room_id else "suite" if "suite" in booking.room_id else "villa"
        )

        now_utc = utcnow()

        # Idempotent check: if already confirmed, return existing confirmation
        if booking.status == "confirmed" and booking.booking_code:
            guest_name = booking.customer.full_name if booking.customer else "Guest"
            guest_email = booking.customer.email if booking.customer else ""
            return {
                "ok": True,
                "status": "confirmed",
                "booking_id": booking.booking_code,
                "booking_code": booking.booking_code,
                "confirmation_number": booking.booking_code,
                "reservation_id": booking.booking_code,
                "guest_name": guest_name,
                "guest_email": guest_email,
                "room_id": booking.room_id,
                "room_name": room_name,
                "room_type": room_type,
                "check_in": booking.check_in.isoformat(),
                "check_out": booking.check_out.isoformat(),
                "guests": booking.guests,
                "total_price": float(booking.total_price),
                "grand_total": float(booking.total_price),
                "currency": getattr(booking, "currency", "USD") or "USD",
                "created_at": booking.created_at.isoformat() if booking.created_at else now_utc.isoformat(),
                "spoken_hint": f"Your booking {booking.booking_code} is already confirmed for {guest_name}."
            }

        # Validate hold expiration
        if booking.hold_expires_at:
            exp_tz = booking.hold_expires_at if booking.hold_expires_at.tzinfo else booking.hold_expires_at.replace(tzinfo=timezone.utc)
            if now_utc > exp_tz:
                booking.status = "expired"
                booking.updated_at = now_utc
                if not caller_owns_session:
                    await session.commit()
                else:
                    await session.flush()
                return {
                    "ok": False,
                    "status": "expired",
                    "error": "Reservation hold has expired.",
                    "spoken_hint": "The courtesy hold on that room has expired. Would you like me to place a fresh hold?"
                }

        # Transition to CONFIRMED
        booking_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
        booking.status = "confirmed"
        booking.booking_code = booking_id
        booking.updated_at = now_utc
        if not caller_owns_session:
            await session.commit()
        else:
            await session.flush()

        guest_name = booking.customer.full_name if booking.customer else "Guest"
        guest_email = booking.customer.email if booking.customer else ""

        # Mirrored memory record
        BOOKINGS_STORE[booking_id] = {
            "booking_id": booking_id,
            "booking_code": booking_id,
            "confirmation_number": booking_id,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "room_id": booking.room_id,
            "room_name": room_name,
            "room_type": room_type,
            "check_in": booking.check_in.isoformat(),
            "check_out": booking.check_out.isoformat(),
            "guests": booking.guests,
            "total_price": float(booking.total_price),
            "grand_total": float(booking.total_price),
            "currency": getattr(booking, "currency", "USD") or "USD",
            "status": "confirmed",
            "created_at": booking.created_at.isoformat() if booking.created_at else now_utc.isoformat()
        }
        if booking.pending_token and booking.pending_token in HOLD_TOKENS_STORE:
            HOLD_TOKENS_STORE[booking.pending_token]["status"] = "confirmed"
            HOLD_TOKENS_STORE[booking.pending_token]["booking_id"] = booking_id
            HOLD_TOKENS_STORE[booking.pending_token]["booking_code"] = booking_id

        logger.info(
            f"[DIAGNOSTICS] save_booking result: booking_id='{booking_id}', "
            f"guest='{guest_name}', room='{room_name}', status='confirmed'"
        )

        spoken_hint = (
            f"Wonderful! Your reservation is officially confirmed! Your confirmation number is {booking_id}. "
            f"I can email your itinerary and receipt now. Would you like me to send that to {guest_email}?"
        )

        res = {
            "ok": True,
            "status": "confirmed",
            "booking_id": booking_id,
            "booking_code": booking_id,
            "confirmation_number": booking_id,
            "reservation_id": booking_id,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "room_id": booking.room_id,
            "room_name": room_name,
            "room_type": room_type,
            "check_in": booking.check_in.isoformat(),
            "check_out": booking.check_out.isoformat(),
            "guests": booking.guests,
            "total_price": float(booking.total_price),
            "grand_total": float(booking.total_price),
            "currency": getattr(booking, "currency", "USD") or "USD",
            "created_at": booking.created_at.isoformat() if booking.created_at else now_utc.isoformat(),
            "spoken_hint": spoken_hint
        }
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            await event_broadcaster.notify_booking_update(res)
        except Exception:
            pass

        return res

    except Exception as exc:
        if not caller_owns_session:
            await session.rollback()
        logger.error(f"Error in save_booking: {exc}", exc_info=True)
        return {
            "ok": False,
            "status": "error",
            "error": f"Reservation system error during confirmation: {type(exc).__name__}: {str(exc)}",
            "spoken_hint": "I apologize, our reservation system encountered an issue while finalizing your booking."
        }
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)



async def get_booking_details(
    booking_identifier: str,
    db_session: Optional[AsyncSession] = None
) -> Optional[dict]:
    """
    Retrieve authoritative booking details from PostgreSQL (or memory mirror)
    by booking_code, confirmation_number, pending_token, or reservation UUID.
    """
    if not booking_identifier:
        return None

    clean_id = str(booking_identifier).strip()
    caller_owns_session = (db_session is not None)
    session_ctx = None if caller_owns_session else AsyncSessionLocal()
    session = db_session if caller_owns_session else await session_ctx.__aenter__()

    try:
        from sqlalchemy import or_
        conditions = [
            Booking.booking_code == clean_id,
            Booking.pending_token == clean_id,
        ]
        try:
            val_uuid = uuid.UUID(clean_id)
            conditions.append(Booking.id == val_uuid)
        except Exception:
            pass

        stmt = (
            select(Booking)
            .options(joinedload(Booking.customer), joinedload(Booking.room))
            .where(or_(*conditions))
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()
        if booking:
            r_name = booking.room.name if booking.room else booking.room_id
            r_type = booking.room.room_type if (booking.room and hasattr(booking.room, "room_type")) else (
                "bungalow" if "bungalow" in booking.room_id else "suite" if "suite" in booking.room_id else "villa"
            )
            g_name = booking.customer.full_name if booking.customer else "Valued Guest"
            g_email = booking.customer.email if booking.customer else ""
            b_code = booking.booking_code or str(booking.id)
            return {
                "ok": True,
                "booking_id": b_code,
                "booking_code": b_code,
                "confirmation_number": b_code,
                "status": booking.status,
                "room_id": booking.room_id,
                "room_name": r_name,
                "room_type": r_type,
                "check_in": booking.check_in.isoformat(),
                "check_out": booking.check_out.isoformat(),
                "guests": booking.guests,
                "total_price": float(booking.total_price),
                "grand_total": float(booking.total_price),
                "currency": getattr(booking, "currency", "USD") or "USD",
                "add_ons": booking.add_ons or [],
                "guest_name": g_name,
                "guest_email": g_email,
            }
    except Exception as exc:
        logger.error(f"Error in get_booking_details: {exc}")
    finally:
        if not caller_owns_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)

    # In-memory fallback
    if clean_id in BOOKINGS_STORE:
        rec = BOOKINGS_STORE[clean_id]
        r_id = rec.get("room_id", "")
        r_type = rec.get("room_type") or ("bungalow" if "bungalow" in r_id else "suite" if "suite" in r_id else "villa")
        return {
            "ok": True,
            "booking_id": rec.get("booking_id"),
            "booking_code": rec.get("booking_code") or rec.get("booking_id"),
            "confirmation_number": rec.get("confirmation_number") or rec.get("booking_id"),
            "status": rec.get("status", "confirmed"),
            "room_id": r_id,
            "room_name": rec.get("room_name", r_id),
            "room_type": r_type,
            "check_in": rec.get("check_in"),
            "check_out": rec.get("check_out"),
            "guests": rec.get("guests", 2),
            "total_price": float(rec.get("total_price", 0.0)),
            "grand_total": float(rec.get("grand_total") or rec.get("total_price", 0.0)),
            "currency": rec.get("currency", "USD"),
            "add_ons": rec.get("add_ons", []),
            "guest_name": rec.get("guest_name", "Valued Guest"),
            "guest_email": rec.get("guest_email", ""),
        }

    if clean_id in HOLD_TOKENS_STORE:
        rec = HOLD_TOKENS_STORE[clean_id]
        r_id = rec.get("room_id", "")
        r_type = rec.get("room_type") or ("bungalow" if "bungalow" in r_id else "suite" if "suite" in r_id else "villa")
        return {
            "ok": True,
            "booking_id": rec.get("booking_id") or clean_id,
            "booking_code": rec.get("booking_id") or clean_id,
            "confirmation_number": rec.get("booking_id") or clean_id,
            "status": rec.get("status", "pending"),
            "room_id": r_id,
            "room_name": rec.get("room_name", r_id),
            "room_type": r_type,
            "check_in": rec.get("check_in"),
            "check_out": rec.get("check_out"),
            "guests": rec.get("guests", 2),
            "total_price": float(rec.get("total_price", 0.0)),
            "grand_total": float(rec.get("grand_total") or rec.get("total_price", 0.0)),
            "currency": rec.get("currency", "USD"),
            "add_ons": rec.get("add_ons", []),
            "guest_name": rec.get("guest_name", "Valued Guest"),
            "guest_email": rec.get("guest_email", ""),
        }

    return None


