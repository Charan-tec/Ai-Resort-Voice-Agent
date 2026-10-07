import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
from app.db.session import AsyncSessionLocal
from app.db.models import Booking, Customer, Room
from app.tools.availability import check_availability
from app.tools.pricing import calculate_price
from app.tools.booking import create_booking, save_booking
from app.tools.email import send_confirmation_email
from app.orchestrator.broadcaster import event_broadcaster
import httpx
from app.main import app


async def run_e2e_verification():
    print("=" * 70)
    print("PHASE 15: COMPLETE END-TO-END RESERVATION WORKFLOW VERIFICATION")
    print("=" * 70)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1 & 2. Verify /health/ready and real PostgreSQL connectivity
        print("\n[Step 1 & 2] Checking /health/ready and PostgreSQL readiness...")
        r_ready = await client.get("/health/ready")
        assert r_ready.status_code == 200, f"Expected 200, got {r_ready.status_code}"
        ready_json = r_ready.json()
        db_status = ready_json.get("providers", {}).get("database", {})
        print(f"  PostgreSQL DB provider: {db_status.get('label')} - configured: {db_status.get('configured')}")
        assert db_status.get("configured") is True, "PostgreSQL must report configured=True"

        # 3. Clean up test dates in PostgreSQL for idempotency
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM bookings WHERE check_in = '2026-10-10';"))
            await session.commit()

        # 4 & 5. User asks: "What rooms are available from October 10th to October 14th for two guests?"
        print("\n[Step 5, 6, 7] Querying real room availability in PostgreSQL (2026-10-10 to 2026-10-14, 2 guests)...")
        avail_res = await check_availability("2026-10-10", "2026-10-14", guests=2)
        print(f"  Available: {avail_res.get('available')}, Count: {avail_res.get('count')}")
        print(f"  Spoken hint: {avail_res.get('spoken_hint')}")
        assert avail_res["ok"] is True
        assert avail_res["available"] is True
        assert avail_res["count"] >= 3
        assert len(avail_res["available_rooms"]) >= 3
        for r in avail_res["available_rooms"]:
            print(f"    - {r['room_name']} (ID: {r['room_id']}, Rate: ${r['nightly_rate']}/night, Capacity: {r['capacity']})")

        # 8 & 9. Guest selects "villa-ocean-101" and calculates price
        print("\n[Step 8 & 9] Calculating real price for 'villa-ocean-101' (4 nights)...")
        price_res = await calculate_price("villa-ocean-101", "2026-10-10", "2026-10-14", add_ons=["breakfast"])
        print(f"  Room: {price_res.get('room')}")
        print(f"  Nights: {price_res.get('nights')}, Nightly Rate: ${price_res.get('nightly_rate')}")
        print(f"  Subtotal: ${price_res.get('subtotal')}")
        print(f"  Resort Fees: ${price_res.get('resort_fees')}")
        print(f"  Tax: ${price_res.get('tax')}")
        print(f"  Add-ons: {price_res.get('add_ons')}")
        print(f"  Total: ${price_res.get('total')}")
        print(f"  Spoken hint: {price_res.get('spoken_hint')}")
        assert price_res["ok"] is True
        assert price_res["nights"] == 4
        assert price_res["total"] > 0
        total_quote = price_res["total"]

        # 10 & 11. Guest confirms booking -> create_booking (HOLD)
        print("\n[Step 10 & 11] Creating booking hold in PostgreSQL...")
        hold_res = await create_booking(
            room_id="villa-ocean-101",
            guest_name="Elena Rostova",
            guest_email="elena.rostova@example.com",
            guest_phone="+18085551234",
            check_in="2026-10-10",
            check_out="2026-10-14",
            total_price=total_quote,
            guests=2,
            add_ons=["breakfast"]
        )
        print(f"  Hold Result: ok={hold_res.get('ok')}, status={hold_res.get('status')}")
        print(f"  Pending Token: {hold_res.get('pending_token')}")
        print(f"  Expires At: {hold_res.get('expires_at')}")
        assert hold_res["ok"] is True
        assert hold_res["status"] == "pending"
        pending_token = hold_res["pending_token"]

        # Verify concurrency protection: Attempting overlapping booking for same room must be rejected
        print("\n[Concurrency Protection] Testing overlapping booking rejection on active hold...")
        conflict_res = await create_booking(
            room_id="villa-ocean-101",
            guest_name="Concurrent Caller",
            guest_email="concurrent@example.com",
            guest_phone="+18085559999",
            check_in="2026-10-12",
            check_out="2026-10-16",
            total_price=1500.0,
            guests=2
        )
        print(f"  Concurrent Booking Blocked: ok={conflict_res.get('ok')}, status={conflict_res.get('status')}")
        assert conflict_res["ok"] is False
        assert conflict_res["status"] == "conflict"
        print("  Exclusion constraint successfully prevented duplicate/overlapping reservation!")

        # 12. Finalize and persist confirmed booking
        print("\n[Step 12] Finalizing and saving confirmed reservation...")
        confirm_res = await save_booking(pending_token=pending_token)
        print(f"  Confirm Result: ok={confirm_res.get('ok')}, status={confirm_res.get('status')}")
        print(f"  Booking Code: {confirm_res.get('booking_code')}")
        print(f"  Spoken hint: {confirm_res.get('spoken_hint')}")
        assert confirm_res["ok"] is True
        assert confirm_res["status"] == "confirmed"
        booking_code = confirm_res["booking_code"]

        # 13. Verify PostgreSQL database record directly
        print("\n[Step 13] Verifying persisted record directly in PostgreSQL database...")
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.room))
                .where(Booking.booking_code == booking_code)
            )
            db_rec = (await session.execute(stmt)).scalar_one_or_none()
            assert db_rec is not None, "Booking must exist in PostgreSQL"
            print(f"  Database Record ID: {db_rec.id}")
            print(f"  Booking Code: {db_rec.booking_code}")
            print(f"  Status: {db_rec.status}")
            print(f"  Room: {db_rec.room.name} ({db_rec.room_id})")
            print(f"  Guest: {db_rec.customer.full_name} ({db_rec.customer.email})")
            print(f"  Dates: {db_rec.check_in} to {db_rec.check_out}")
            print(f"  Guests: {db_rec.guests}")
            print(f"  Total Price: ${db_rec.total_price:.2f}")
            assert db_rec.status == "confirmed"
            assert db_rec.check_in == date(2026, 10, 10)
            assert db_rec.check_out == date(2026, 10, 14)

        # 14. Send confirmation email
        print("\n[Step 14] Sending confirmation email via async worker...")
        email_res = await send_confirmation_email(booking_code, "elena.rostova@example.com")
        print(f"  Email Result: ok={email_res.get('ok')}, email_status={email_res.get('email_status')}")
        print(f"  Spoken hint: {email_res.get('spoken_hint')}")
        assert email_res["ok"] is True
        assert email_res["email_status"] == "sent"

        # 15. Verify dashboard API endpoints return real state
        print("\n[Step 15] Verifying recruiter dashboard APIs...")
        r_bookings = await client.get("/api/bookings")
        assert r_bookings.status_code == 200
        recent = r_bookings.json().get("bookings", [])
        assert len(recent) > 0
        top_booking = recent[0]
        print(f"  Dashboard Recent Booking: {top_booking.get('booking_code')} for {top_booking.get('guest_name')} ({top_booking.get('room_name')})")
        assert top_booking.get("booking_code") == booking_code

        r_state = await client.get("/api/agent/state")
        assert r_state.status_code == 200
        state_json = r_state.json()
        print(f"  Dashboard Agent State session_state: {state_json.get('session_state')}")

        print("\n" + "=" * 70)
        print("ALL 16 VERIFICATION STEPS PASSED SUCCESSFULLY!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
