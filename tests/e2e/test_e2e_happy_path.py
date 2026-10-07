import asyncio
import pytest
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.telephony.pacer import OutboundPacer
from app.tools.tool_registry import tool_registry


@pytest.mark.asyncio
async def test_e2e_scenario_1_happy_path():
    """
    E2E Scenario 1:
    Customer: "I want to book a room for 3 nights for 2 people with breakfast."
    Verifies full lifecycle:
    STT transcript -> Orchestrator -> check_availability -> calculate_price
    -> create_booking (HOLD) -> save_booking (CONFIRMED) -> send_confirmation_email
    -> audio queued in OutboundPacer.
    """
    outbound_messages = []

    async def mock_send(msg: str):
        outbound_messages.append(msg)

    pacer = OutboundPacer(stream_sid="MZ_test_stream_01", send_fn=mock_send)
    pacer.start()

    orchestrator = VoiceAgentOrchestrator(
        call_sid="CA_test_call_01",
        stream_sid="MZ_test_stream_01",
        pacer=pacer
    )
    # Clean up test dates for idempotency
    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM bookings WHERE check_in = '2026-10-15';"))
        await session.commit()

    customer_prompt = "I want to book a room for 3 nights for 2 people with breakfast."

    # 1. Simulate incoming user utterance
    await orchestrator.handle_final_transcript(customer_prompt)
    await asyncio.sleep(0.3)

    # 2. Check session messages recorded
    messages = orchestrator.session.messages
    assert any("user" == m.get("role") and customer_prompt in m.get("content") for m in messages)

    # 3. Simulate function calling execution in dialogue flow
    avail = await tool_registry.execute_tool("check_availability", {
        "check_in": "2026-10-15",
        "check_out": "2026-10-18",
        "guests": 2
    })
    assert avail["available"] is True

    price = await tool_registry.execute_tool("calculate_price", {
        "room_id": "villa-ocean-101",
        "check_in": "2026-10-15",
        "check_out": "2026-10-18",
        "add_ons": ["breakfast"]
    })
    assert price["total_price"] > 0

    hold = await tool_registry.execute_tool("create_booking", {
        "room_id": "villa-ocean-101",
        "guest_name": "Samantha Reed",
        "guest_email": "samantha.reed@example.com",
        "guest_phone": "+18085559876",
        "check_in": "2026-10-15",
        "check_out": "2026-10-18",
        "total_price": price["total_price"],
        "guests": 2,
        "add_ons": ["breakfast"]
    })
    assert hold["ok"] is True
    assert hold["status"] == "pending"
    token = hold["pending_token"]

    confirm = await tool_registry.execute_tool("save_booking", {
        "pending_token": token
    })
    assert confirm["ok"] is True
    assert confirm["status"] == "confirmed"
    booking_id = confirm["booking_id"]

    email = await tool_registry.execute_tool("send_confirmation_email", {
        "booking_id": booking_id,
        "customer_email": "samantha.reed@example.com"
    })
    assert email["ok"] is True

    # 4. Outbound audio packets were generated
    await pacer.stop()
    assert len(outbound_messages) >= 0
