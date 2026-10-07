from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.orchestrator.prompts import SYSTEM_PROMPT


class SessionState:
    """
    Maintains caller conversation state, booking progress, and transcript truncation mapping.
    Also tracks conversational context: active dates, guest counts, room selections, pricing, and intent.
    """

    def __init__(self, call_sid: str, stream_sid: str):
        self.call_sid = call_sid
        self.stream_sid = stream_sid

        # Conversation history initialized with system prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Active booking state
        self.active_pending_token: Optional[str] = None
        self.confirmed_booking_id: Optional[str] = None
        self.confirmed_booking_data: Optional[dict] = None
        self.guest_name: Optional[str] = None
        self.guest_email: Optional[str] = None
        self.guest_phone: Optional[str] = None

        # Conversational context
        self.check_in: Optional[str] = None
        self.check_out: Optional[str] = None
        self.date_error: Optional[str] = None
        self.guests: int = 2
        self.selected_room_id: Optional[str] = None
        self.selected_room_name: Optional[str] = None
        self.available_rooms: List[dict] = []
        self.last_pricing: Optional[dict] = None
        self.selected_country: Optional[str] = None
        self.selected_currency: str = "USD"
        self.current_intent: Optional[str] = None
        self.last_assistant_question: Optional[str] = None
        self.has_greeted: bool = False

        # Tracking for assistant turn truncation on barge-in
        self.current_turn_sentences: List[dict] = []  # list of {"text": str, "mark_id": str}
        self.is_turn_in_progress: bool = False

    @property
    def active_check_in(self) -> Optional[str]:
        return self.check_in

    @property
    def active_check_out(self) -> Optional[str]:
        return self.check_out

    @property
    def active_guests(self) -> int:
        return self.guests

    @property
    def selected_room(self) -> Optional[str]:
        return self.selected_room_id

    @property
    def last_available_rooms(self) -> List[dict]:
        return self.available_rooms

    @last_available_rooms.setter
    def last_available_rooms(self, val: List[dict]):
        self.available_rooms = val

    def update_context_from_utterance(self, text: str):
        """Extract and update dates, guest count, and room entities from caller speech."""
        import re
        from app.utils.date_parser import parse_date_range
        lower = text.lower()

        # Date extraction using robust natural language parser
        ci, co, err = parse_date_range(text)
        if err:
            self.date_error = err
            self.check_in = None
            self.check_out = None
            self.available_rooms = []
            self.selected_room_id = None
            self.selected_room_name = None
            self.last_pricing = None
            self.active_pending_token = None
        elif ci and co:
            self.date_error = None
            if ci != self.check_in or co != self.check_out:
                self.check_in = ci
                self.check_out = co
                # When dates change dynamically, clear stale room/pricing data
                self.available_rooms = []
                self.selected_room_id = None
                self.selected_room_name = None
                self.last_pricing = None
                self.active_pending_token = None
        elif ci and not co:
            self.date_error = None
            if self.check_in and ci > self.check_in:
                self.check_out = ci
                self.available_rooms = []
                self.selected_room_id = None
                self.selected_room_name = None
                self.last_pricing = None
                self.active_pending_token = None
            else:
                self.check_in = ci
                if not self.check_out:
                    self.check_out = None
        else:
            # Fallback regex for standard ISO YYYY-MM-DD
            match = re.search(r'(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})', lower)
            if match:
                new_ci, new_co = match.group(1), match.group(2)
                if new_ci != self.check_in or new_co != self.check_out:
                    self.check_in = new_ci
                    self.check_out = new_co
                    self.date_error = None
                    self.available_rooms = []
                    self.selected_room_id = None
                    self.selected_room_name = None
                    self.last_pricing = None
                    self.active_pending_token = None

        # Guest count extraction
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10
        }
        for w, val in word_to_num.items():
            if (f"{w} guest" in lower or f"{w} people" in lower or f"{w} person" in lower or 
                f"for {w}" in lower or f"party of {w}" in lower):
                self.guests = val
                break

        # Room entity extraction (all 6 rooms supported)
        has_explicit_room = False
        if any(k in lower for k in ("presidential ocean suite", "presidential suite", "presidential")):
            self.selected_room_id = "suite-presidential-401"
            self.selected_room_name = "Presidential Ocean Suite"
            has_explicit_room = True
        elif any(k in lower for k in ("family pool villa", "family villa", "pool villa")):
            self.selected_room_id = "villa-family-501"
            self.selected_room_name = "Family Pool Villa"
            has_explicit_room = True
        elif any(k in lower for k in ("premium garden suite", "premium suite", "premium garden")):
            self.selected_room_id = "suite-premium-302"
            self.selected_room_name = "Premium Garden Suite"
            has_explicit_room = True
        elif any(k in lower for k in ("oceanfront luxury villa", "luxury villa", "oceanfront villa", "villa")):
            self.selected_room_id = "villa-ocean-101"
            self.selected_room_name = "Oceanfront Luxury Villa"
            has_explicit_room = True
        elif any(k in lower for k in ("deluxe sunset suite", "sunset suite", "deluxe suite", "suite")):
            self.selected_room_id = "suite-deluxe-201"
            self.selected_room_name = "Deluxe Sunset Suite"
            has_explicit_room = True
        elif any(k in lower for k in ("garden tropical bungalow", "tropical bungalow", "garden bungalow", "bungalow")):
            self.selected_room_id = "bungalow-garden-301"
            self.selected_room_name = "Garden Tropical Bungalow"
            has_explicit_room = True

        # Intent tracking & contextual selection
        cheapest_phrases = (
            "cheapest", "which room is cheapest", "which is cheapest", "which one is cheapest",
            "what's the cheapest", "whats the cheapest", "give me the cheapest", "lowest price",
            "lowest rate", "cheapest option", "cheapest room", "least expensive", "which one is cheaper",
            "which is cheaper", "lowest cost"
        )
        if any(p in lower for p in cheapest_phrases):
            self.current_intent = "cheapest_room_comparison"
            if self.available_rooms:
                sorted_rooms = sorted(
                    self.available_rooms,
                    key=lambda r: float(r.get("nightly_rate") or r.get("base_rate_nightly") or 99999)
                )
                self.selected_room_id = sorted_rooms[0]["room_id"]
                self.selected_room_name = sorted_rooms[0]["name"]
            else:
                self.selected_room_id = "bungalow-garden-301"
                self.selected_room_name = "Garden Tropical Bungalow"
        elif any(k in lower for k in ("available", "availability", "rooms available", "vacancies", "room for", "rooms for", "need a room", "need rooms", "what rooms", "looking for a room")) or (ci and co and not any(k in lower for k in ("book", "reserve", "hold", "price", "how much", "cost"))):
            self.current_intent = "availability"
        elif any(k in lower for k in (
            "price details", "price detail", "pricing details", "pricing detail",
            "how much is my booking", "how much is the booking", "what is the total",
            "what's the total", "whats the total", "breakdown", "price breakdown",
            "cost breakdown", "how much do i pay", "how much do i owe", "how much will it cost",
            "can you share me the price details", "share me the price details",
            "share price details", "tell me the price", "price", "how much", "cost", "rate", "quote"
        )):
            self.current_intent = "pricing"
            # If there is an active confirmed booking, preserve the booked room unless user named another room
            if self.confirmed_booking_data and self.confirmed_booking_data.get("room_id") and not has_explicit_room:
                self.selected_room_id = self.confirmed_booking_data["room_id"]
                if self.confirmed_booking_data.get("room_name"):
                    self.selected_room_name = self.confirmed_booking_data["room_name"]
        elif any(k in lower for k in ("book that one", "book that", "book it", "reserve that", "reserve it", "book the cheapest", "book the cheapest one", "book", "reserve", "hold")):
            self.current_intent = "booking"
            if self.available_rooms and not self.selected_room_id:
                sorted_rooms = sorted(
                    self.available_rooms,
                    key=lambda r: float(r.get("nightly_rate") or r.get("base_rate_nightly") or 99999)
                )
                self.selected_room_id = sorted_rooms[0]["room_id"]
                self.selected_room_name = sorted_rooms[0]["name"]
            elif not self.selected_room_id:
                self.selected_room_id = "bungalow-garden-301"
                self.selected_room_name = "Garden Tropical Bungalow"

    def update_context_from_tool(self, tool_name: str, args: dict, result: dict):
        """Update context with authoritative tool execution results."""
        if tool_name == "check_availability" and isinstance(result, dict):
            if result.get("check_in"):
                self.check_in = result["check_in"]
            if result.get("check_out"):
                self.check_out = result["check_out"]
            if result.get("guests"):
                self.guests = result["guests"]
            self.available_rooms = result.get("available_rooms", [])
            # If a room was previously selected but is not available, reset it
            if self.selected_room_id and self.available_rooms:
                avail_ids = [r.get("room_id") for r in self.available_rooms]
                if self.selected_room_id not in avail_ids:
                    self.selected_room_id = None
                    self.selected_room_name = None

        elif tool_name == "calculate_price" and isinstance(result, dict):
            self.last_pricing = result
            if result.get("room_id"):
                self.selected_room_id = result["room_id"]
            if result.get("room_name") or result.get("room"):
                self.selected_room_name = result.get("room_name") or result.get("room")

        elif tool_name == "create_booking" and isinstance(result, dict):
            if result.get("pending_token"):
                self.active_pending_token = result["pending_token"]
            if result.get("room_id"):
                self.selected_room_id = result["room_id"]
            if result.get("room_name"):
                self.selected_room_name = result["room_name"]
            if result.get("check_in"):
                self.check_in = result["check_in"]
            if result.get("check_out"):
                self.check_out = result["check_out"]
            if result.get("guests"):
                self.guests = result["guests"]
            self.confirmed_booking_data = dict(result)

        elif tool_name == "save_booking" and isinstance(result, dict):
            b_code = result.get("confirmation_number") or result.get("booking_code") or result.get("booking_id")
            if b_code and b_code.lower() != "confirmed":
                self.confirmed_booking_id = b_code
            if result.get("room_id"):
                self.selected_room_id = result["room_id"]
            if result.get("room_name"):
                self.selected_room_name = result["room_name"]
            if result.get("check_in"):
                self.check_in = result["check_in"]
            if result.get("check_out"):
                self.check_out = result["check_out"]
            if result.get("guests"):
                self.guests = result["guests"]
            self.confirmed_booking_data = dict(result)

        self.refresh_system_prompt_context()

    def get_context_summary(self) -> str:
        """Generate a concise context reminder to guide the LLM."""
        items = []
        if self.date_error:
            items.append(f"Date validation error: {self.date_error}")
        if self.check_in and self.check_out:
            items.append(f"Active dates: {self.check_in} to {self.check_out}")
        if self.guests:
            items.append(f"Guests: {self.guests}")
        if self.selected_room_name:
            items.append(f"Selected room: {self.selected_room_name} ({self.selected_room_id})")
        if self.available_rooms:
            names = [f"{r.get('name', r.get('room_id'))} (${r.get('nightly_rate', r.get('base_rate_nightly', 0))}/night)" for r in self.available_rooms]
            items.append(f"Recently verified available rooms: {', '.join(names)}")
        if self.last_pricing:
            items.append(f"Last calculated total: ${self.last_pricing.get('total_price', 0)} USD")
        if self.active_pending_token:
            items.append(f"Active pending hold token: {self.active_pending_token}")
        if self.confirmed_booking_id:
            items.append(f"Confirmed booking code / confirmation number: {self.confirmed_booking_id}")
            if self.selected_room_name:
                items.append(f"Confirmed booked room: {self.selected_room_name} ({self.selected_room_id})")
        return "; ".join(items) if items else "No active booking context yet."

    def refresh_system_prompt_context(self):
        """Update the system message with current conversational state."""
        ctx_summary = self.get_context_summary()
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = (
                f"{SYSTEM_PROMPT}\n\n"
                f"CURRENT CONVERSATIONAL CONTEXT (RETAIN THESE DETAILS; DO NOT RE-ASK ACTIVE DATES/GUESTS):\n"
                f"{ctx_summary}"
            )

    def add_user_message(self, text: str):
        """Append guest utterance to conversation history."""
        self.update_context_from_utterance(text)
        self.refresh_system_prompt_context()
        self.messages.append({"role": "user", "content": text})

    def start_assistant_turn(self):
        """Prepare for assistant turn generation."""
        self.current_turn_sentences.clear()
        self.is_turn_in_progress = True

    def record_sentence_chunk(self, sentence: str, mark_id: str):
        """Record chunk and its associated Twilio mark ID for precision playback tracking."""
        self.current_turn_sentences.append({
            "text": sentence,
            "mark_id": mark_id
        })

    def complete_assistant_turn(self, full_text: str):
        """Called when assistant finishes speaking without interruption."""
        self.is_turn_in_progress = False
        self.messages.append({"role": "assistant", "content": full_text})
        self.current_turn_sentences.clear()

    def truncate_on_barge_in(self, last_acked_mark: Optional[str]) -> str:
        """
        Truncates the assistant's message to only the text the guest actually heard
        prior to interrupting, avoiding LLM context hallucination.
        """
        self.is_turn_in_progress = False
        if not self.current_turn_sentences:
            return ""

        heard_sentences = []
        if last_acked_mark:
            for item in self.current_turn_sentences:
                heard_sentences.append(item["text"])
                if item["mark_id"] == last_acked_mark:
                    break
        else:
            # Guest barged in before first mark ACK; at most the first few words were heard
            if self.current_turn_sentences:
                first_sent = self.current_turn_sentences[0]["text"]
                words = first_sent.split()[:4]
                heard_sentences.append(" ".join(words) + "...")

        heard_text = " ".join(heard_sentences).strip()
        if heard_text:
            logger.info(f"SessionState: Assistant transcript truncated to heard text: '{heard_text}'")
            self.messages.append({"role": "assistant", "content": heard_text + " [interrupted]"})
        self.current_turn_sentences.clear()
        return heard_text

    def reset_conversation(self):
        """
        Completely reset conversational messages, interim turn tracking, and context slots.
        Strictly preserves database bookings and resort catalog knowledge.
        """
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.active_pending_token = None
        self.confirmed_booking_id = None
        self.confirmed_booking_data = None
        self.guest_name = None
        self.guest_email = None
        self.guest_phone = None
        self.check_in = None
        self.check_out = None
        self.guests = 2
        self.selected_room_id = None
        self.selected_room_name = None
        self.available_rooms = []
        self.last_pricing = None
        self.current_intent = None
        self.last_assistant_question = None
        self.has_greeted = False
        self.current_turn_sentences.clear()
        self.is_turn_in_progress = False
        logger.info(f"SessionState reset for call_sid: {self.call_sid}")

