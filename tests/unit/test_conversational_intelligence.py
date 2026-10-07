import asyncio
import json
import pytest
from app.llm.gemini import GeminiLLMProvider
from app.orchestrator.session import SessionState
from app.orchestrator.prompts import SYSTEM_PROMPT
from app.tools.tool_registry import tool_registry
from app.tools.retrieval import search_resort_knowledge


@pytest.fixture
def llm():
    return GeminiLLMProvider()


@pytest.fixture
def tools():
    return tool_registry.get_tool_definitions()


@pytest.fixture
def fresh_session():
    return SessionState(call_sid="test_call_conv", stream_sid="test_stream_conv")


# ==============================================================================
# Test 1: Caller: "What time is check-in?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_1_check_in_time(llm, tools, fresh_session):
    fresh_session.add_user_message("What time is check-in?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    # Must trigger RAG knowledge search or directly return grounded answer
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    if tool_calls:
        assert tool_calls[0]["name"] == "search_resort_knowledge"
        rag_res = await tool_registry.execute_tool(tool_calls[0]["name"], tool_calls[0]["arguments"])
        fresh_session.messages.append({"role": "function", "name": "search_resort_knowledge", "content": json.dumps(rag_res)})
        followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
        text = "".join(f["content"] for f in followup if f.get("type") == "token")
    else:
        text = "".join(e["content"] for e in events if e.get("type") == "token")

    assert "3:00 PM" in text or "3:00 pm" in text.lower()
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 2: Caller: "What time is check-out?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_2_check_out_time(llm, tools, fresh_session):
    fresh_session.add_user_message("What time is check-out?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    if tool_calls:
        assert tool_calls[0]["name"] == "search_resort_knowledge"
        rag_res = await tool_registry.execute_tool(tool_calls[0]["name"], tool_calls[0]["arguments"])
        fresh_session.messages.append({"role": "function", "name": "search_resort_knowledge", "content": json.dumps(rag_res)})
        followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
        text = "".join(f["content"] for f in followup if f.get("type") == "token")
    else:
        text = "".join(e["content"] for e in events if e.get("type") == "token")

    assert "11:00 AM" in text or "11:00 am" in text.lower()
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 3: Caller: "What rooms are available for two guests from October 1st to October 4th?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_3_availability_with_dates(llm, tools, fresh_session):
    fresh_session.add_user_message("What rooms are available for two guests from October 1st to October 4th?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    assert len(tool_calls) > 0
    assert tool_calls[0]["name"] == "check_availability"
    assert tool_calls[0]["arguments"]["check_in"] == "2026-10-01"
    assert tool_calls[0]["arguments"]["check_out"] == "2026-10-04"
    assert tool_calls[0]["arguments"]["guests"] == 2

    # Execute tool
    avail_res = await tool_registry.execute_tool("check_availability", tool_calls[0]["arguments"])
    assert avail_res["ok"] is True
    assert avail_res["available"] is True
    
    fresh_session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res)})
    followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
    text = "".join(f["content"] for f in followup if f.get("type") == "token")
    assert "Deluxe Sunset Suite" in text or "Garden Tropical Bungalow" in text or "options available" in text
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 4: Caller: "How much is the Deluxe Sunset Suite?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_4_pricing_deluxe_sunset_suite(llm, tools, fresh_session):
    fresh_session.add_user_message("How much is the Deluxe Sunset Suite?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    assert len(tool_calls) > 0
    assert tool_calls[0]["name"] == "calculate_price"
    assert "suite" in tool_calls[0]["arguments"]["room_id"]

    price_res = await tool_registry.execute_tool("calculate_price", tool_calls[0]["arguments"])
    assert price_res["ok"] is True
    assert price_res["total_price"] > 0
    
    fresh_session.messages.append({"role": "function", "name": "calculate_price", "content": json.dumps(price_res)})
    followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
    text = "".join(f["content"] for f in followup if f.get("type") == "token")
    assert "Deluxe Sunset Suite" in text
    assert "$380" in text or str(int(price_res["total_price"])) in text or "$" in text
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 5: Caller: "Do you allow pets?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_5_pet_policy(llm, tools, fresh_session):
    fresh_session.add_user_message("Do you allow pets?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    if tool_calls:
        assert tool_calls[0]["name"] == "search_resort_knowledge"
        rag_res = await tool_registry.execute_tool("search_resort_knowledge", tool_calls[0]["arguments"])
        fresh_session.messages.append({"role": "function", "name": "search_resort_knowledge", "content": json.dumps(rag_res)})
        followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
        text = "".join(f["content"] for f in followup if f.get("type") == "token")
    else:
        text = "".join(e["content"] for e in events if e.get("type") == "token")

    assert "pets are not permitted" in text.lower() or "not permitted" in text.lower()
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 6: Caller: "What restaurants do you have?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_6_restaurants(llm, tools, fresh_session):
    fresh_session.add_user_message("What restaurants do you have?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    if tool_calls:
        assert tool_calls[0]["name"] == "search_resort_knowledge"
        rag_res = await tool_registry.execute_tool("search_resort_knowledge", tool_calls[0]["arguments"])
        fresh_session.messages.append({"role": "function", "name": "search_resort_knowledge", "content": json.dumps(rag_res)})
        followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
        text = "".join(f["content"] for f in followup if f.get("type") == "token")
    else:
        text = "".join(e["content"] for e in events if e.get("type") == "token")

    assert "azure ocean grill" in text.lower() or "dining" in text.lower() or "palm terrace" in text.lower()
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 7: Multi-turn: "What rooms are available?" -> asks for dates -> "October 1st to October 4th."
# ==============================================================================
@pytest.mark.asyncio
async def test_question_7_availability_multi_turn_dates(llm, tools, fresh_session):
    # Turn 1: User asks without dates
    fresh_session.add_user_message("What rooms are available?")
    events1 = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    text1 = "".join(e["content"] for e in events1 if e.get("type") == "token")
    
    # Must ask for dates
    assert "dates" in text1.lower() or "planning" in text1.lower()
    fresh_session.complete_assistant_turn(text1)

    # Turn 2: User provides dates
    fresh_session.add_user_message("October 1st to October 4th.")
    events2 = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    tool_calls2 = [e for e in events2 if e.get("type") == "tool_call"]
    
    # Must remember original availability intent and execute check_availability!
    assert len(tool_calls2) > 0
    assert tool_calls2[0]["name"] == "check_availability"
    assert tool_calls2[0]["arguments"]["check_in"] == "2026-10-01"
    assert tool_calls2[0]["arguments"]["check_out"] == "2026-10-04"


# ==============================================================================
# Test 8: Multi-turn: "What rooms are available for two guests?" -> options -> "Which one is cheaper?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_8_which_one_is_cheaper(llm, tools, fresh_session):
    fresh_session.add_user_message("What rooms are available for two guests from October 1st to October 4th?")
    avail_res = await tool_registry.execute_tool("check_availability", {"check_in": "2026-10-01", "check_out": "2026-10-04", "guests": 2})
    fresh_session.messages.append({"role": "function", "name": "check_availability", "content": json.dumps(avail_res)})
    fresh_session.complete_assistant_turn("We have two options available for those dates: the Deluxe Sunset Suite and Garden Tropical Bungalow.")

    # User asks comparison
    fresh_session.add_user_message("Which one is cheaper?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    text = "".join(e["content"] for e in events if e.get("type") == "token")
    
    assert "garden tropical bungalow" in text.lower() or "bungalow" in text.lower()
    assert "cheaper" in text.lower() or "290" in text
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 9: Contextual reference: "How much is the suite?"
# ==============================================================================
@pytest.mark.asyncio
async def test_question_9_how_much_is_the_suite(llm, tools, fresh_session):
    fresh_session.add_user_message("How much is the suite?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    
    assert len(tool_calls) > 0
    assert tool_calls[0]["name"] == "calculate_price"
    # Must resolve "the suite" to Deluxe Sunset Suite
    assert "suite" in tool_calls[0]["arguments"]["room_id"]


# ==============================================================================
# Test 10: "I want to book the Oceanfront Luxury Villa."
# ==============================================================================
@pytest.mark.asyncio
async def test_question_10_booking_flow_start(llm, tools, fresh_session):
    fresh_session.add_user_message("I want to book the Oceanfront Luxury Villa.")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    tokens = [e["content"] for e in events if e.get("type") == "token"]
    text = "".join(tokens)
    
    # Either starts collecting missing dates or triggers create_booking
    if tool_calls:
        assert tool_calls[0]["name"] in ("create_booking", "check_availability", "calculate_price")
        assert "villa" in str(tool_calls[0]["arguments"])
    else:
        assert "dates" in text.lower() or "oceanfront luxury villa" in text.lower() or "delighted" in text.lower()
    
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 11: Room service question
# ==============================================================================
@pytest.mark.asyncio
async def test_question_room_service(llm, tools, fresh_session):
    fresh_session.add_user_message("Do you have room service?")
    events = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=tools)]
    
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    if tool_calls:
        assert tool_calls[0]["name"] == "search_resort_knowledge"
        rag_res = await tool_registry.execute_tool("search_resort_knowledge", tool_calls[0]["arguments"])
        fresh_session.messages.append({"role": "function", "name": "search_resort_knowledge", "content": json.dumps(rag_res)})
        followup = [chunk async for chunk in llm.stream_chat(fresh_session.messages, tools=None)]
        text = "".join(f["content"] for f in followup if f.get("type") == "token")
    else:
        text = "".join(e["content"] for e in events if e.get("type") == "token")

    assert "24-hour" in text or "room service" in text.lower() or "in-room dining" in text.lower()
    assert "welcome to azure paradise resort" not in text.lower()


# ==============================================================================
# Test 12: Knowledge not found: Never invent information
# ==============================================================================
@pytest.mark.asyncio
async def test_knowledge_not_found():
    res = await search_resort_knowledge("Can I bring my elephant?")
    assert "I don't have that information in the resort information available to me" in res["spoken_hint"]
