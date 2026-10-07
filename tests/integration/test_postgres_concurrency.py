import asyncio
from datetime import date
import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Booking, Room

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_postgres_exclusion_constraint_concurrency(pg_engine):
    """
    Mandatory PostgreSQL 16 Concurrency Test:
    Verifies that the btree_gist exclusion constraint on (room_id WITH =, daterange(...) WITH &&)
    genuinely and strictly prevents concurrent overlapping reservations for the same room.

    Expected:
      Exactly ONE transaction succeeds.
      Exactly ONE transaction fails with IntegrityError (exclusion_violation SQLSTATE 23P01).
      success_count == 1
      failure_count == 1
    """
    session_factory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # 1. Seed test room idempotently and clear test dates
    from sqlalchemy import text
    async with session_factory() as session:
        test_room = await session.get(Room, "villa-ocean-101")
        if not test_room:
            test_room = Room(
                id="villa-ocean-101",
                name="Oceanfront Luxury Villa",
                room_type="villa",
                max_occupancy=4,
                base_rate=650.0,
                is_active=True
            )
            session.add(test_room)
        await session.execute(
            text("DELETE FROM bookings WHERE room_id = 'villa-ocean-101' AND check_in >= '2026-11-01' AND check_out <= '2026-11-07';")
        )
        await session.commit()

    success_count = 0
    failure_count = 0
    failure_reasons = []

    # 2. Define concurrent booking attempt
    async def attempt_booking(guest_name: str, check_in: date, check_out: date):
        nonlocal success_count, failure_count
        async with session_factory() as session:
            booking = Booking(
                id=uuid.uuid4(),
                booking_code=f"RES-{uuid.uuid4().hex[:6].upper()}",
                room_id="villa-ocean-101",
                check_in=check_in,
                check_out=check_out,
                status="confirmed",
                total_price=1300.0
            )
            session.add(booking)
            try:
                # Commit the transaction
                await session.commit()
                success_count += 1
            except IntegrityError as exc:
                await session.rollback()
                failure_count += 1
                failure_reasons.append(str(exc))
            except Exception as exc:
                await session.rollback()
                failure_count += 1
                failure_reasons.append(str(exc))

    # 3. Launch 2 genuinely concurrent tasks with overlapping dates
    # Task A: Nov 1 to Nov 5
    # Task B: Nov 3 to Nov 7 (Overlaps Nov 3 - Nov 5)
    t1 = asyncio.create_task(attempt_booking("Guest Alice", date(2026, 11, 1), date(2026, 11, 5)))
    t2 = asyncio.create_task(attempt_booking("Guest Bob", date(2026, 11, 3), date(2026, 11, 7)))

    await asyncio.gather(t1, t2)

    # 4. Strict assertions
    assert success_count == 1, f"Expected exactly 1 booking to succeed, but got {success_count}"
    assert failure_count == 1, f"Expected exactly 1 booking to fail from exclusion constraint, but got {failure_count}"

    # Verify that the failure was caused by the exclusion constraint
    err_str = failure_reasons[0].lower()
    assert "exclusion" in err_str or "no_overlapping_bookings" in err_str or "23p01" in err_str, (
        f"Expected failure to be exclusion constraint violation, but got: {failure_reasons[0]}"
    )
