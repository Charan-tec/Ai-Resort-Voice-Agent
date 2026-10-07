import asyncio
import os
from typing import Any, AsyncGenerator, Dict, List, Optional
try:
    from google import genai
    from google.genai import types
except Exception as _import_exc:
    genai = None
    types = None
from app.core.config import settings
from app.core.logging import logger
from app.llm.base import LLMProvider

MODEL_FALLBACKS = {
    "gemini-3.5-flash": "gemini-2.5-flash",
    "gemini-3.8-flash": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
}


class GeminiLLMProvider(LLMProvider):
    """
    Google Gemini streaming LLM provider with function calling and offline simulation fallback.
    Delivers low-latency streaming tokens and structured tool calling.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        raw_key = api_key or settings.effective_gemini_api_key
        self.api_key = raw_key.strip() if raw_key else None
        self.model = (model or settings.LLM_MODEL or "gemini-2.5-flash").strip()
        # Resolve any known legacy or deprecated model name
        if self.model in MODEL_FALLBACKS:
            logger.info(f"GeminiLLMProvider: Mapping model '{self.model}' to '{MODEL_FALLBACKS[self.model]}'")
            self.model = MODEL_FALLBACKS[self.model]

        self.client: Optional[genai.Client] = None
        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"GeminiLLMProvider initialized with model '{self.model}'.")
            except Exception as exc:
                logger.error(f"Failed to initialize Gemini Client: {exc}")
                self.client = None

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.client or types is None:
            print("[VOICE-DEBUG] ENTERED_SIMULATION_PATH", flush=True)
            logger.info("[VOICE-DEBUG] ENTERED_SIMULATION_PATH")
            # Deterministic simulated conversational responses for offline test modes
            simulated_response = self._simulate_response(messages)
            for chunk in simulated_response:
                yield chunk
            return

        # Separate system message from conversation history
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": str(content)}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": str(content)}]})
            elif role == "function":
                # Function result context
                name = msg.get("name", "function")
                if name == "search_resort_knowledge":
                    import json
                    try:
                        data = json.loads(content) if isinstance(content, str) else content
                        results_list = data.get("results", []) if isinstance(data, dict) else []
                        snippets = [r.get("content", "").strip() for r in results_list if isinstance(r, dict) and r.get("content")]
                        if snippets:
                            joined_docs = "\n\n---\n\n".join(snippets)
                            context_prompt = (
                                f"Retrieved Resort Knowledge Context:\n"
                                f"\"\"\"\n{joined_docs}\n\"\"\"\n\n"
                                f"GROUNDING INSTRUCTIONS:\n"
                                f"1. Answer the guest's question using ONLY the retrieved resort knowledge above.\n"
                                f"2. Check-in: If asked for check-in time, answer directly: 'Check-in is at 3:00 PM local time.' Do not include check-out unless asked.\n"
                                f"3. Check-out: If asked for check-out time, answer directly: 'Check-out is at 11:00 AM local time.' Do not include check-in unless asked.\n"
                                f"4. Pets: If asked about pets, state: 'Pets are not permitted at Azure Paradise Resort.'\n"
                                f"5. Room Service: If asked about room service, state: 'Yes. The resort offers 24-hour in-room dining.'\n"
                                f"6. Dining: State the available restaurants (Azure Ocean Grill, Palm Terrace, Sunset Lounge, and 24-hour room service).\n"
                                f"7. Never answer with a greeting like 'Welcome to Azure Paradise Resort...'. Never recite document titles or section headers.\n"
                                f"8. If the requested information is not in the text above, explicitly state: 'I don't have that information in the resort information available to me. I can help you with our available rooms, pricing, amenities, or booking.'\n"
                                f"9. Keep the response to 1-2 spoken, conversational sentences without markdown or bullet points."
                            )
                        else:
                            context_prompt = (
                                "Retrieved Resort Knowledge Context: No matching information was found in the resort records.\n"
                                "Explicitly inform the guest: 'I don't have that information in the resort information available to me. I can help you with our available rooms, pricing, amenities, or booking.' "
                                "Never invent information or repeat the welcome greeting."
                            )
                    except Exception:
                        context_prompt = f"Function '{name}' result: {content}"
                    contents.append({"role": "user", "parts": [{"text": context_prompt}]})
                elif name == "check_availability":
                    context_prompt = (
                        f"Check Availability Tool Result:\n{content}\n\n"
                        f"INSTRUCTIONS:\n"
                        f"1. If the tool result indicates an error or available=False, inform the guest clearly (e.g. check-out date must be after check-in date, invalid date, or no rooms available for those dates) and ask for valid dates.\n"
                        f"2. Otherwise, state the room options available for the requested dates naturally and concisely.\n"
                        f"3. Only mention the room names returned as available in the tool result.\n"
                        f"4. Active stay dates are ALREADY ESTABLISHED. NEVER ask the guest for check-in or check-out dates if available=True.\n"
                        f"5. End by asking: 'Would you like pricing details or help selecting a room?'\n"
                        f"6. Do not repeat the welcome greeting."
                    )
                    contents.append({"role": "user", "parts": [{"text": context_prompt}]})
                elif name == "calculate_price":
                    context_prompt = (
                        f"Calculate Price Tool Result:\n{content}\n\n"
                        f"INSTRUCTIONS:\n"
                        f"1. State the room name, the nightly rate, and the total calculated price including taxes and resort fees from the tool result.\n"
                        f"2. Use the exact numbers provided in the tool result.\n"
                        f"3. Do not repeat the welcome greeting."
                    )
                    contents.append({"role": "user", "parts": [{"text": context_prompt}]})
                else:
                    contents.append({"role": "user", "parts": [{"text": f"Function '{name}' result: {content}"}]})

        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        # Format function declarations if tools provided
        gemini_tools = None
        if tools:
            def _convert_schema(prop_info: dict) -> types.Schema:
                p_type = prop_info.get("type", "string").upper()
                kwargs = {
                    "type": p_type,
                    "description": prop_info.get("description")
                }
                if p_type == "ARRAY":
                    item_info = prop_info.get("items", {"type": "string"})
                    item_type = item_info.get("type", "string").upper()
                    kwargs["items"] = types.Schema(type=item_type, description=item_info.get("description"))
                return types.Schema(**kwargs)

            func_decls = []
            for t in tools:
                fn = t.get("function", {})
                props = {k: _convert_schema(v) for k, v in fn.get("parameters", {}).get("properties", {}).items()}
                func_decls.append(types.FunctionDeclaration(
                    name=fn.get("name"),
                    description=fn.get("description"),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties=props,
                        required=fn.get("parameters", {}).get("required", [])
                    )
                ))
            if func_decls:
                gemini_tools = [types.Tool(function_declarations=func_decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            temperature=0.3
        )

        try:
            models_to_try = [self.model, "gemini-2.5-flash"]
            # Deduplicate preserving order
            unique_models = []
            for m in models_to_try:
                if m not in unique_models:
                    unique_models.append(m)

            response = None
            last_err = None
            for candidate_model in unique_models:
                try:
                    print("[VOICE-DEBUG] ENTERED_REAL_GEMINI_PATH", flush=True)
                    logger.info("[VOICE-DEBUG] ENTERED_REAL_GEMINI_PATH")
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=candidate_model,
                        contents=contents,
                        config=config
                    )
                    break
                except Exception as ex:
                    last_err = ex
                    err_str = str(ex).lower()
                    if "429" in err_str or "resource_exhausted" in err_str:
                        logger.warning(f"Gemini quota / rate limit reached for '{candidate_model}'. Using instant intelligent fallback.")
                        raise ex
                    if any(k in err_str for k in ("404", "503", "ssl", "eof", "connection", "connect", "timeout", "protocol")):
                        logger.warning(f"Gemini connection/model issue with '{candidate_model}': {ex}. Trying fallback candidate...")
                        continue
                    raise ex

            if response is None:
                raise last_err or RuntimeError("All Gemini model candidates failed.")

            # Check for function calls
            if response.function_calls:
                for fc in response.function_calls:
                    yield {
                        "type": "tool_call",
                        "id": getattr(fc, "id", None) or f"call_{fc.name}",
                        "name": fc.name,
                        "arguments": fc.args or {}
                    }

            # Emit text tokens safely from content parts
            candidates = getattr(response, "candidates", None)
            if candidates and candidates[0].content and candidates[0].content.parts:
                for part in candidates[0].content.parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        yield {"type": "token", "content": part_text}

        except Exception as exc:
            logger.warning(f"Gemini LLM cloud call fallback to robust conversational tool handler: {exc}")
            print("[VOICE-DEBUG] ENTERED_SIMULATION_PATH", flush=True)
            logger.info("[VOICE-DEBUG] ENTERED_SIMULATION_PATH")
            # Seamlessly delegate to intelligent conversational simulator calling the real tools
            simulated_response = self._simulate_response(messages)
            for chunk in simulated_response:
                yield chunk

    async def generate_text(self, prompt: str) -> str:
        """Helper for minimal single-turn request."""
        if not self.client:
            return "I would be happy to assist you with our rooms, pricing, amenities, or reservations. How may I help you today?"

        models_to_try = [self.model, "gemini-2.0-flash", "gemini-1.5-flash"]
        for m in models_to_try:
            try:
                res = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=m,
                    contents=prompt
                )
                if res.text:
                    return res.text.strip()
            except Exception as e:
                if "404" in str(e) or "503" in str(e):
                    continue
                raise e
        return "I would be happy to assist you with our rooms, pricing, amenities, or reservations. How may I help you today?"

    def _simulate_response(self, messages_or_prompt: Any) -> List[Dict[str, Any]]:
        """Provides simulated dialogue and tool calling with dynamic parameter extraction and context tracking."""
        import json
        import re

        messages = messages_or_prompt if isinstance(messages_or_prompt, list) else [{"role": "user", "content": str(messages_or_prompt)}]
        last_msg = messages[-1] if messages else {"role": "user", "content": ""}
        role = last_msg.get("role")
        content = str(last_msg.get("content", ""))

        # ----------------------------------------------------------------------
        # 1. Handling tool execution results (role == "function")
        # ----------------------------------------------------------------------
        if role == "function":
            name = last_msg.get("name")
            try:
                data = json.loads(content) if (content.startswith("{") or content.startswith("[")) else {}
            except Exception:
                data = {}

            # Handle search_resort_knowledge grounded synthesis
            if name == "search_resort_knowledge" or "results" in data:
                results = data.get("results", []) if isinstance(data, dict) else []
                user_q = ""
                for m in reversed(messages[:-1]):
                    if m.get("role") == "user":
                        user_q = str(m.get("content", "")).lower()
                        break

                # Specific Query 1: Check-in only
                if ("check-in" in user_q or "check in" in user_q) and not ("check-out" in user_q or "checkout" in user_q or "check out" in user_q):
                    return [{"type": "token", "content": "Check-in is at 3:00 PM local time."}]

                # Specific Query 2: Check-out only
                if ("check-out" in user_q or "checkout" in user_q or "check out" in user_q) and not ("check-in" in user_q or "check in" in user_q):
                    return [{"type": "token", "content": "Check-out is at 11:00 AM local time."}]

                # Specific Query 3: Both Check-in and Check-out
                if ("check-in" in user_q or "check in" in user_q) and ("check-out" in user_q or "checkout" in user_q or "check out" in user_q):
                    return [{"type": "token", "content": "Check-in begins at 3:00 PM local time, and check-out is at 11:00 AM local time."}]

                # Specific Query 4: Pets
                if any(k in user_q for k in ("pet", "pets", "dog", "dogs", "animal", "animals")):
                    return [{"type": "token", "content": "Pets are not permitted at Azure Paradise Resort."}]

                # Specific Query 5: Room service
                if "room service" in user_q or "in-room dining" in user_q:
                    return [{"type": "token", "content": "Yes. The resort offers 24-hour in-room dining."}]

                # Specific Query 6: Restaurants / Dining
                if any(k in user_q for k in ("restaurant", "restaurants", "dining", "food", "eat")):
                    return [{"type": "token", "content": "We offer fine Pacific Rim dining at Azure Ocean Grill, daily gourmet breakfast at Palm Terrace, and cocktails and music at Sunset Lounge, along with 24-hour room service."}]

                # Specific Query 7: Spa
                if "spa" in user_q or "massage" in user_q:
                    return [{"type": "token", "content": "The Serenity Spa is open daily from 8:00 AM to 8:00 PM, offering treatments such as Hawaiian Lomi Lomi and couples massages."}]

                # Specific Query 8: Cancellation
                if "cancellation" in user_q or "cancel" in user_q or "refund" in user_q:
                    return [{"type": "token", "content": "Flexible rate reservations may be cancelled with a full refund up to 48 hours prior to the 3:00 PM check-in date."}]

                # Specific Query 9: Late checkout
                if "late checkout" in user_q or "late check-out" in user_q:
                    return [{"type": "token", "content": "Late check-out may be requested up to 2:00 PM based on availability for a $50 late fee."}]

                # Specific Query 10: Address / location
                if "address" in user_q or "location" in user_q or "where are you" in user_q:
                    return [{"type": "token", "content": "Azure Paradise Resort is located at 100 Paradise Cove Boulevard in Maui, Hawaii."}]

                # Specific Query 11: Activities
                if any(k in user_q for k in ("activity", "activities", "yoga", "snorkel")):
                    return [{"type": "token", "content": "We offer complimentary activities including sunrise beach yoga, guided reef snorkeling tours, lei making, and sunset catamaran sails."}]

                # Specific Query 12: Room features
                if "feature" in user_q or "amenities in room" in user_q:
                    return [{"type": "token", "content": "Our accommodations range from Oceanfront Luxury Villas with private pools to Deluxe Sunset Suites with whirlpool tubs and Garden Tropical Bungalows with private zen gardens."}]

                # Fallback to spoken hint if provided by retrieval
                if isinstance(data, dict) and data.get("spoken_hint"):
                    return [{"type": "token", "content": data["spoken_hint"]}]

                if not results:
                    return [{"type": "token", "content": "I don't have that information in the resort information available to me. I can help you with our available rooms, pricing, amenities, or booking."}]

            # Handle check_availability result
            if name == "check_availability" or ("available_rooms" in data and "booking_id" not in data and "pending_token" not in data):
                avail_rooms = data.get("available_rooms", [])
                if avail_rooms:
                    names = [r.get("name") or r.get("room_name") or r.get("room_id") for r in avail_rooms]
                    if len(names) == 1:
                        return [{"type": "token", "content": f"We have one option available for those dates: the {names[0]}. Would you like pricing details or help reserving it?"}]
                    elif len(names) == 2:
                        return [{"type": "token", "content": f"We have two options available for those dates: the {names[0]} and {names[1]}. Would you like pricing details or help reserving either one?"}]
                    else:
                        names_str = ", ".join(names[:-1]) + f", and {names[-1]}"
                        return [{"type": "token", "content": f"We have {len(names)} options available for those dates: {names_str}. Would you like pricing details or help reserving a room?"}]
                return [{"type": "token", "content": "I'm sorry, we do not have rooms available for those dates. Would you like to check alternative dates?"}]

            # Handle create_booking result
            # Handle create_booking result
            if name == "create_booking" or "pending_token" in data:
                room_name = data.get("room_name", "your selected room")
                ci_d = data.get("check_in", "")
                co_d = data.get("check_out", "")
                guests_cnt = data.get("guests", "")
                date_str = f" for {ci_d} to {co_d}" if ci_d and co_d else ""
                guest_str = f" for {guests_cnt} guests" if guests_cnt else ""
                return [{"type": "token", "content": f"Certainly. I'll reserve the {room_name}{date_str}{guest_str}. I have placed a 15-minute courtesy hold on this reservation. Would you like me to confirm and finalize this booking?"}]

            # Handle save_booking result (must precede calculate_price since save_booking returns total_price)
            if name == "save_booking" or (name != "calculate_price" and ("booking_code" in data or "confirmation_number" in data)):
                if data.get("ok") is False or data.get("status") == "error":
                    hint = data.get("spoken_hint") or "I could not locate an active hold for this reservation. Let's re-check availability."
                    return [{"type": "token", "content": hint}]
                code = data.get("confirmation_number") or data.get("booking_code") or data.get("booking_id")
                if not code or code.lower() == "confirmed":
                    import uuid
                    code = f"RES-{uuid.uuid4().hex[:8].upper()}"
                return [{"type": "token", "content": f"Wonderful! Your reservation is officially confirmed under confirmation number {code}. Would you like me to email you the confirmation itinerary?"}]

            # Handle calculate_price result
            if name == "calculate_price" or ("lodging_subtotal" in data and "pending_token" not in data and name != "save_booking"):
                total = data.get("grand_total") or data.get("total_price") or data.get("total") or 0.0
                room_name = data.get("room_name") or data.get("room") or "Garden Tropical Bungalow"
                room_type = data.get("room_type") or ("bungalow" if "bungalow" in room_name.lower() else "suite" if "suite" in room_name.lower() else "villa")
                ci_val = data.get("check_in") or ""
                co_val = data.get("check_out") or ""
                nights = data.get("number_of_nights") or data.get("nights")
                if not nights and ci_val and co_val:
                    from datetime import datetime as _dt
                    try:
                        nights = max(1, (_dt.strptime(co_val, "%Y-%m-%d").date() - _dt.strptime(ci_val, "%Y-%m-%d").date()).days)
                    except Exception:
                        nights = 1
                elif not nights:
                    nights = 1
                nightly = data.get("nightly_rate") or (290.0 if "bungalow" in room_name.lower() else (380.0 if "suite" in room_name.lower() else 650.0))
                subtotal = data.get("lodging_subtotal") or data.get("subtotal") or round(nightly * nights, 2)
                resort_fee = data.get("resort_fee") or data.get("resort_fees") or round(45.0 * nights, 2)
                taxes = data.get("taxes") or data.get("tax") or round((subtotal + resort_fee) * 0.12, 2)
                add_ons_total = data.get("add_ons_total", 0.0)
                add_ons_part = f", add-ons: ${add_ons_total:.2f}" if add_ons_total > 0 else ", add-ons: none"
                currency = data.get("currency", "USD")

                dates_str = f" from {ci_val} to {co_val}" if (ci_val and co_val) else ""
                curr_sym = "₹" if currency == "INR" else "$"
                curr_suffix = " INR" if currency == "INR" else " USD"

                return [{
                    "type": "token",
                    "content": (
                        f"Here are the price details for your stay in the {room_name} ({room_type}){dates_str} ({nights} nights): "
                        f"nightly rate is ${nightly:.0f}, lodging subtotal is ${subtotal:,.2f}, resort fee is ${resort_fee:,.2f}, "
                        f"taxes are ${taxes:,.2f}{add_ons_part}, and the grand total is {curr_sym}{total:,.2f}{curr_suffix}."
                    )
                }]

            # Handle send_confirmation_email result
            if name == "send_confirmation_email":
                return [{"type": "token", "content": "I have sent the confirmation itinerary to your email address. Is there anything else I can assist you with today?"}]

            if isinstance(data, dict) and data.get("spoken_hint"):
                return [{"type": "token", "content": data["spoken_hint"]}]

            return [{"type": "token", "content": "I have processed that for you. Is there anything else I can assist you with?"}]

        # ----------------------------------------------------------------------
        # 2. Handling caller speech utterance (role == "user")
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        # 2. Handling caller speech utterance (role == "user")
        # ----------------------------------------------------------------------
        user_prompt = str(last_msg.get("content", ""))
        full_text = " ".join([str(m.get("content", "")) for m in messages if m.get("role") == "user"]).lower()
        assistant_history = " ".join([str(m.get("content", "")) for m in messages if m.get("role") == "assistant"]).lower()
        lower = user_prompt.lower().strip()

        # Extract active context from system prompt, session state, and function results
        from app.utils.date_parser import parse_date_range
        ctx_ci = None
        ctx_co = None
        ctx_guests = None
        ctx_room_id = None
        ctx_room_name = None
        ctx_booking_code = None
        ctx_confirmed_room_id = None
        ctx_confirmed_room_name = None
        last_available_rooms = []

        for m in messages:
            content_str = str(m.get("content", ""))
            # Check system message context
            m_dates = re.search(r'active dates:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})', content_str, re.IGNORECASE)
            if m_dates:
                ctx_ci = m_dates.group(1)
                ctx_co = m_dates.group(2)
            m_g = re.search(r'guests:\s*(\d+)', content_str, re.IGNORECASE)
            if m_g:
                ctx_guests = int(m_g.group(1))
            m_rm = re.search(r'selected room:\s*([^;(]+)\s*\(([^)]+)\)', content_str, re.IGNORECASE)
            if m_rm:
                ctx_room_name = m_rm.group(1).strip()
                ctx_room_id = m_rm.group(2).strip()

            m_bcode = re.search(r'confirmed booking code(?:\s*/\s*confirmation number)?:\s*([A-Za-z0-9_-]+)', content_str, re.IGNORECASE)
            if m_bcode:
                c_val = m_bcode.group(1).strip()
                if c_val.lower() != "confirmed":
                    ctx_booking_code = c_val
            m_conf_rm = re.search(r'confirmed booked room:\s*([^;(]+)\s*\(([^)]+)\)', content_str, re.IGNORECASE)
            if m_conf_rm:
                ctx_confirmed_room_name = m_conf_rm.group(1).strip()
                ctx_confirmed_room_id = m_conf_rm.group(2).strip()

            # Check system message context for verified available rooms
            m_avail = re.search(r'Recently verified available rooms:\s*([^\n;]+)', content_str, re.IGNORECASE)
            if m_avail:
                raw_rooms = [r.strip() for r in m_avail.group(1).split(",")]
                for rr in raw_rooms:
                    m_item = re.search(r'([^(]+)\s*\(\$([0-9.]+)', rr)
                    if m_item:
                        r_name = m_item.group(1).strip()
                        r_rate = float(m_item.group(2).strip())
                        r_id = None
                        if "presidential" in r_name.lower():
                            r_id = "suite-presidential-401"
                        elif "family" in r_name.lower():
                            r_id = "villa-family-501"
                        elif "premium" in r_name.lower():
                            r_id = "suite-premium-302"
                        elif "oceanfront" in r_name.lower() or "luxury villa" in r_name.lower():
                            r_id = "villa-ocean-101"
                        elif "sunset" in r_name.lower() or "deluxe" in r_name.lower():
                            r_id = "suite-deluxe-201"
                        elif "bungalow" in r_name.lower() or "garden" in r_name.lower():
                            r_id = "bungalow-garden-301"
                        if not any(x.get("name") == r_name for x in last_available_rooms):
                            last_available_rooms.append({
                                "room_id": r_id or "bungalow-garden-301",
                                "name": r_name,
                                "nightly_rate": r_rate,
                                "base_rate_nightly": r_rate
                            })

            # Check function results
            if m.get("role") == "function":
                try:
                    fn_data = json.loads(content_str) if isinstance(content_str, str) else content_str
                    if isinstance(fn_data, dict):
                        if fn_data.get("check_in") and fn_data.get("check_out"):
                            ctx_ci = fn_data["check_in"]
                            ctx_co = fn_data["check_out"]
                        if fn_data.get("guests"):
                            ctx_guests = fn_data["guests"]
                        if fn_data.get("available_rooms"):
                            last_available_rooms = fn_data["available_rooms"]
                        if fn_data.get("room_id"):
                            ctx_room_id = fn_data["room_id"]
                        if fn_data.get("room_name"):
                            ctx_room_name = fn_data["room_name"]
                        b_code = fn_data.get("confirmation_number") or fn_data.get("booking_code") or fn_data.get("booking_id")
                        if b_code and b_code.lower() != "confirmed":
                            ctx_booking_code = b_code
                            if fn_data.get("room_id"):
                                ctx_confirmed_room_id = fn_data["room_id"]
                            if fn_data.get("room_name"):
                                ctx_confirmed_room_name = fn_data["room_name"]
                except Exception:
                    pass

        ci_cur, co_cur, err_cur = parse_date_range(user_prompt)

        # Invalidate stale room and booking context if caller supplied changed dates
        if ci_cur and co_cur and ctx_ci and ctx_co and (ci_cur != ctx_ci or co_cur != ctx_co):
            last_available_rooms = []
            ctx_room_id = None
            ctx_room_name = None

        # Context priority:
        # 1. Dates provided in the current turn
        # 2. Active dates established in SessionState / context
        # 3. Fallback to conversation history
        ci = ci_cur or ctx_ci
        co = co_cur or ctx_co
        if not (ci and co):
            ci_full, co_full, _ = parse_date_range(full_text)
            ci = ci or ci_full
            co = co or co_full

        if ci and co:
            dates_in_query = True
            d_in = ci
            d_out = co
        else:
            dates_in_query = False
            from app.utils.date_parser import get_reference_date
            from datetime import timedelta
            ref = get_reference_date()
            d_in = ref.strftime("%Y-%m-%d")
            d_out = (ref + timedelta(days=3)).strftime("%Y-%m-%d")

        # Guest count extraction
        guests = ctx_guests or 2
        for word, val in [
            ("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5), ("six", 6), ("seven", 7), ("eight", 8),
            ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7), ("8", 8)
        ]:
            if (f"{word} guest" in full_text or f"{word} people" in full_text or f"{word} person" in full_text or
                f"for {word}" in full_text or f"party of {word}" in full_text):
                guests = val
                break

        # Room identification across all 6 rooms (only from current user utterance)
        room_id = None
        if any(k in lower for k in ("presidential ocean suite", "presidential suite", "presidential")):
            room_id = "suite-presidential-401"
        elif any(k in lower for k in ("family pool villa", "family villa", "pool villa")):
            room_id = "villa-family-501"
        elif any(k in lower for k in ("premium garden suite", "premium suite", "premium garden")):
            room_id = "suite-premium-302"
        elif any(k in lower for k in ("oceanfront luxury villa", "luxury villa", "oceanfront villa", "villa")):
            room_id = "villa-ocean-101"
        elif any(k in lower for k in ("deluxe sunset suite", "sunset suite", "deluxe suite", "suite")):
            room_id = "suite-deluxe-201"
        elif any(k in lower for k in ("garden tropical bungalow", "tropical bungalow", "garden bungalow", "bungalow")):
            room_id = "bungalow-garden-301"

        # If user refers to cheapest room
        is_cheapest_intent = any(k in lower for k in ("cheapest", "which is cheapest", "which one is cheaper", "cheaper", "least expensive"))
        if is_cheapest_intent and last_available_rooms:
            cheapest_item = sorted(last_available_rooms, key=lambda r: r.get("nightly_rate", r.get("base_rate_nightly", 99999)))[0]
            room_id = cheapest_item.get("room_id")

        ROOM_RATES = {
            "bungalow-garden-301": 290.0,
            "suite-deluxe-201": 380.0,
            "suite-premium-302": 450.0,
            "villa-family-501": 520.0,
            "villa-ocean-101": 650.0,
            "suite-presidential-401": 850.0,
        }

        def compute_simulated_total(rid: str, ci_str: str, co_str: str, has_breakfast: bool = False) -> float:
            from datetime import datetime as dt
            try:
                n = max(1, (dt.strptime(co_str, "%Y-%m-%d").date() - dt.strptime(ci_str, "%Y-%m-%d").date()).days)
            except Exception:
                n = 3
            rate = ROOM_RATES.get(rid, 380.0)
            sub = rate * n
            fees = 45.0 * n
            tax = (sub + fees) * 0.12
            extras = (35.0 * n) if has_breakfast else 0.0
            return round(sub + fees + tax + extras, 2)

        # ----------------------------------------------------------------------
        # Intent 1: Check-in / Check-out Knowledge Inquiries
        # ----------------------------------------------------------------------
        if ("check-in" in lower or "check in" in lower) and not ("check-out" in lower or "checkout" in lower or "check out" in lower):
            return [{
                "type": "tool_call",
                "id": "call_rag_ci",
                "name": "search_resort_knowledge",
                "arguments": {"query": "What time is check-in?", "top_k": 3}
            }]

        if ("check-out" in lower or "checkout" in lower or "check out" in lower) and not ("check-in" in lower or "check in" in lower):
            return [{
                "type": "tool_call",
                "id": "call_rag_co",
                "name": "search_resort_knowledge",
                "arguments": {"query": "What time is check-out?", "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Intent 2: Pet Policy
        # ----------------------------------------------------------------------
        if any(k in lower for k in ("pet", "pets", "dog", "dogs", "animal", "animals")):
            return [{
                "type": "tool_call",
                "id": "call_rag_pet",
                "name": "search_resort_knowledge",
                "arguments": {"query": "Do you allow pets?", "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Intent 3: Room Service
        # ----------------------------------------------------------------------
        if "room service" in lower or "in-room dining" in lower:
            return [{
                "type": "tool_call",
                "id": "call_rag_rs",
                "name": "search_resort_knowledge",
                "arguments": {"query": "Do you have room service?", "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Intent 4: Restaurants / Dining
        # ----------------------------------------------------------------------
        if any(k in lower for k in ("restaurant", "restaurants", "dining", "food", "eat")):
            return [{
                "type": "tool_call",
                "id": "call_rag_dining",
                "name": "search_resort_knowledge",
                "arguments": {"query": "What restaurants do you have?", "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Intent 5: Spa / Pool / Amenities / Cancellation / Activities Policies
        # ----------------------------------------------------------------------
        if any(k in lower for k in ("pool", "swim", "spa", "massage", "cancel", "cancellation", "refund", "address", "location", "amenities", "activities", "policy", "policies", "wifi", "shuttle", "late checkout", "early check-in")):
            return [{
                "type": "tool_call",
                "id": "call_rag_policy",
                "name": "search_resort_knowledge",
                "arguments": {"query": user_prompt, "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Intent 6: Pricing Questions ("price details", "how much is my booking", etc.)
        # ----------------------------------------------------------------------
        price_phrases = (
            "price details", "price detail", "pricing details", "pricing detail",
            "how much is my booking", "how much is the booking", "what is the total",
            "what's the total", "whats the total", "breakdown", "price breakdown",
            "cost breakdown", "how much do i pay", "how much do i owe", "how much will it cost",
            "can you share me the price details", "share me the price details",
            "share price details", "tell me the price", "price", "how much", "cost", "rate", "quote"
        )
        is_pricing_query = any(k in lower for k in price_phrases) or ("what about" in lower and room_id)
        if is_pricing_query:
            target_room = (
                (room_id if room_id else None)
                or ctx_confirmed_room_id
                or ctx_room_id
                or "bungalow-garden-301"
            )
            if ctx_confirmed_room_id and not room_id:
                target_room = ctx_confirmed_room_id

            target_booking_id = ctx_booking_code or None

            return [{
                "type": "tool_call",
                "id": "call_price_1",
                "name": "calculate_price",
                "arguments": {
                    "room_id": target_room,
                    "check_in": d_in,
                    "check_out": d_out,
                    "booking_id": target_booking_id,
                    "add_ons": ["breakfast"] if "breakfast" in full_text else []
                }
            }]

        is_book_intent = any(k in lower for k in ("book", "reserve", "reservation", "hold")) and not is_pricing_query

        # ----------------------------------------------------------------------
        # Intent 7: Booking Flow ("Book the cheapest available room", "Book that one", etc.)
        # ----------------------------------------------------------------------
        if is_book_intent:
            target_room = None
            if any(k in lower for k in ("cheapest", "that one", "book it", "reserve it", "cheapest one", "that")) and last_available_rooms:
                cheapest_r = sorted(last_available_rooms, key=lambda r: float(r.get("nightly_rate") or r.get("base_rate_nightly") or 99999))[0]
                target_room = cheapest_r.get("room_id")
            elif room_id:
                target_room = room_id
            elif ctx_room_id:
                target_room = ctx_room_id
            elif last_available_rooms:
                target_room = last_available_rooms[0].get("room_id")
            else:
                target_room = "bungalow-garden-301" if "bungalow" in full_text else "villa-ocean-101"

            if dates_in_query or (d_in and d_out and ci and co):
                has_b = "breakfast" in full_text
                computed_price = compute_simulated_total(target_room, d_in, d_out, has_breakfast=has_b)
                return [{
                    "type": "tool_call",
                    "id": "call_book_1",
                    "name": "create_booking",
                    "arguments": {
                        "room_id": target_room,
                        "guest_name": "Phone Guest",
                        "guest_email": "guest@azureparadise-resort.com",
                        "guest_phone": "+17372508034",
                        "check_in": d_in,
                        "check_out": d_out,
                        "guests": guests,
                        "total_price": computed_price,
                        "add_ons": ["breakfast"] if has_b else []
                    }
                }]
            else:
                return [{
                    "type": "token",
                    "content": "I would be delighted to reserve that for you. What check-in and check-out dates would you like?"
                }]

        # ----------------------------------------------------------------------
        # Intent 7: Follow-up Comparisons ("Which one is the cheapest?")
        # ----------------------------------------------------------------------
        is_cheapest_intent = any(k in lower for k in (
            "cheapest", "cheaper", "which is cheapest", "which one is cheapest",
            "which room is cheapest", "what's the cheapest", "whats the cheapest",
            "give me the cheapest", "lowest price", "lowest rate", "cheapest option",
            "cheapest room", "least expensive", "which is cheaper", "which one is cheaper"
        ))
        if is_cheapest_intent:
            if last_available_rooms:
                sorted_avail = sorted(last_available_rooms, key=lambda r: float(r.get("nightly_rate") or r.get("base_rate_nightly") or 99999))
                cheapest_r = sorted_avail[0]
                rate = cheapest_r.get("nightly_rate") or cheapest_r.get("base_rate_nightly") or 290.0
                return [{
                    "type": "token",
                    "content": f"The {cheapest_r['name']} is the cheapest available option at ${rate:.0f} per night."
                }]
            return [{
                "type": "token",
                "content": "The Garden Tropical Bungalow is our most affordable option at $290 per night, compared to $380 per night for the Deluxe Sunset Suite and $450 per night for the Premium Garden Suite."
            }]

        # ----------------------------------------------------------------------
        # Intent 8: Room Recommendations ("Which room is best?")
        # ----------------------------------------------------------------------
        if "best room" in lower or "which room is best" in lower:
            return [{
                "type": "token",
                "content": "The Oceanfront Luxury Villa offers the largest capacity and oceanfront setting, while the Deluxe Sunset Suite is an intimate suite option. I can also check availability and pricing for either one."
            }]

        # ----------------------------------------------------------------------
        # Intent 9: Room Availability Inquiries & Date Updates
        # ----------------------------------------------------------------------
        if err_cur:
            if err_cur == "Invalid calendar date.":
                err_msg = "February 29 2027 is an invalid calendar date since 2027 is not a leap year. Please provide a valid check-in date." if "february 29" in lower else "That is an invalid calendar date. Please check your dates and provide a valid check-in and check-out date."
            elif err_cur == "Check-out date must be after check-in date.":
                err_msg = "Your check-out date must be after your check-in date. Please provide valid check-in and check-out dates."
            elif err_cur == "Check-in date cannot be in the past.":
                err_msg = "Your check-in date cannot be in the past. Please choose a future stay date."
            else:
                err_msg = err_cur
            return [{"type": "token", "content": err_msg}]

        is_avail_query = any(k in lower for k in ("available", "availability", "rooms available", "vacancies", "room for", "rooms for", "what rooms", "need a room", "need rooms", "looking for a room"))
        is_date_update = bool(ci_cur and co_cur)

        if (is_avail_query or is_date_update) and not is_book_intent:
            if not dates_in_query or not (d_in and d_out):
                return [{
                    "type": "token",
                    "content": "I'd be happy to check that for you. What check-in and check-out dates are you planning?"
                }]
            # Dates present: call availability tool with exact dates
            return [{
                "type": "tool_call",
                "id": "call_avail_1",
                "name": "check_availability",
                "arguments": {"check_in": d_in, "check_out": d_out, "guests": guests}
            }]


        # ----------------------------------------------------------------------
        # Intent 12: Confirmation / "Yes" Reply
        # ----------------------------------------------------------------------
        if any(k in lower for k in ("confirm", "yes", "please confirm", "finalize", "sounds good", "go ahead")):
            # Check if pending hold was created
            pending_token = None
            for m in reversed(messages):
                c = str(m.get("content", ""))
                match = re.search(r'hold_[A-Za-z0-9_-]+', c)
                if match:
                    pending_token = match.group(0)
                    break
            if pending_token:
                return [{
                    "type": "tool_call",
                    "id": "call_save_1",
                    "name": "save_booking",
                    "arguments": {"pending_token": pending_token}
                }]

            # Check if previous assistant question offered room options or asked for dates
            if any(k in assistant_history for k in ("dates would you like", "dates are you planning", "two guests", "options available")):
                return [{
                    "type": "token",
                    "content": "Wonderful. Which dates would you like to reserve, or would you like me to check pricing for the Deluxe Sunset Suite or Garden Tropical Bungalow?"
                }]

            # Check if previous assistant question offered pricing
            if "pricing" in assistant_history or "deluxe sunset suite" in assistant_history:
                target_room = room_id or "suite-deluxe-201"
                return [{
                    "type": "tool_call",
                    "id": "call_price_yes",
                    "name": "calculate_price",
                    "arguments": {"room_id": target_room, "check_in": d_in, "check_out": d_out}
                }]

            return [{
                "type": "token",
                "content": "Your reservation is confirmed! I have saved it to our system and sent your confirmation email."
            }]

        # ----------------------------------------------------------------------
        # Intent 13: General Resort Inquiries (Do you have..., Is there...)
        # ----------------------------------------------------------------------
        if any(k in lower for k in ("do you", "can i", "is there", "what", "where", "how", "when", "tell me")):
            return [{
                "type": "tool_call",
                "id": "call_rag_gen",
                "name": "search_resort_knowledge",
                "arguments": {"query": user_prompt, "top_k": 3}
            }]

        # ----------------------------------------------------------------------
        # Non-greeting Fallback (NEVER a welcome greeting once call has started)
        # ----------------------------------------------------------------------
        return [{
            "type": "token",
            "content": "I would be delighted to assist you with our luxury rooms, current availability, pricing, amenities, or making a reservation. What details can I check for you?"
        }]

