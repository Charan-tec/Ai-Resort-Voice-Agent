import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from app.core.logging import logger


class EventBroadcaster:
    """
    Central in-memory event bus and state broadcaster for the Resort AI Voice Agent.
    Maintains connected UI dashboard WebSockets and broadcasts live telephony events:
    transcripts, agent states (LISTENING/THINKING/SPEAKING/BARGED_IN), tool calls,
    RAG retrieval activities, and booking updates.
    """

    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

        # Cached state snapshot for instant UI hydration on connection
        self.state: Dict[str, Any] = {
            "agent_status": "ONLINE",
            "session_state": "IDLE",  # IDLE, LISTENING, THINKING, SPEAKING, BARGED_IN
            "active_call": None,  # {call_sid, stream_sid, caller_number, started_at}
            "last_barge_in": None,  # {latency_ms, timestamp}
            "conversation": [],  # list of {role, content, timestamp, is_final, mark_id}
            "current_tool": None,  # {name, args, result, timestamp, status}
            "last_rag": None,  # {query, docs, timestamp}
            "active_booking": None,  # {guest_name, room_id, check_in, check_out, guests, total_price, status, booking_code}
            "metrics": {
                "total_turns": 0,
                "total_tool_calls": 0,
                "barge_in_count": 0,
                "last_active": None
            }
        }

    async def register(self, websocket: WebSocket):
        """Register a new UI dashboard WebSocket client."""
        async with self._lock:
            self._clients.add(websocket)
            logger.info(f"Broadcaster: Registered dashboard client. Total active: {len(self._clients)}")

        # Send current full snapshot immediately to hydrate the client
        try:
            await websocket.send_text(json.dumps({
                "event": "snapshot",
                "data": self.get_snapshot()
            }))
        except Exception as exc:
            logger.debug(f"Broadcaster: Failed to send initial snapshot: {exc}")

    async def unregister(self, websocket: WebSocket):
        """Unregister a disconnected dashboard client."""
        async with self._lock:
            self._clients.discard(websocket)
            logger.info(f"Broadcaster: Unregistered client. Remaining active: {len(self._clients)}")

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a copy of the current state snapshot."""
        return dict(self.state)

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event payload to all connected dashboard WebSockets."""
        message = json.dumps({"event": event_type, "data": data, "timestamp": time.time()})

        async with self._lock:
            if not self._clients:
                return

            dead_clients = set()
            for client in list(self._clients):
                try:
                    await client.send_text(message)
                except Exception:
                    dead_clients.add(client)

            for dead in dead_clients:
                self._clients.discard(dead)

    # --------------------------------------------------------------------------
    # Specialized Notification Helpers
    # --------------------------------------------------------------------------

    async def notify_call_started(self, call_sid: str, stream_sid: str, caller_number: Optional[str] = None):
        call_info = {
            "call_sid": call_sid,
            "stream_sid": stream_sid,
            "caller_number": caller_number or "Inbound PSTN Caller",
            "started_at": time.time()
        }
        self.state["active_call"] = call_info
        self.state["session_state"] = "LISTENING"
        self.state["metrics"]["last_active"] = time.time()
        await self.broadcast("call_started", call_info)

    async def notify_call_ended(self, call_sid: str, stream_sid: str):
        ended_info = {
            "call_sid": call_sid,
            "stream_sid": stream_sid,
            "ended_at": time.time()
        }
        self.state["active_call"] = None
        self.state["session_state"] = "IDLE"
        await self.broadcast("call_ended", ended_info)

    async def notify_session_state(self, new_state: str):
        self.state["session_state"] = new_state
        self.state["metrics"]["last_active"] = time.time()
        await self.broadcast("session_state_changed", {"session_state": new_state})

    async def notify_user_transcript(self, text: str, is_final: bool = False, turn_id: Optional[str] = None):
        entry = {
            "role": "user",
            "content": text,
            "turn_id": turn_id,
            "is_final": is_final,
            "timestamp": time.time()
        }
        if is_final:
            # Check if this turn_id is already committed
            if turn_id and any(m.get("turn_id") == turn_id for m in self.state["conversation"]):
                logger.debug(f"Broadcaster: Skipping duplicate final turn_id: {turn_id}")
                return

            # Check if last user message is identical or near-duplicate refinement
            last_msg = next((m for m in reversed(self.state["conversation"]) if m.get("role") == "user"), None)
            if last_msg:
                last_text = last_msg.get("content", "").strip().lower()
                new_text = text.strip().lower()
                time_since_last = time.time() - last_msg.get("timestamp", 0)

                if last_text == new_text and time_since_last < 5.0:
                    logger.debug(f"Broadcaster: Skipping duplicate final user message: {text}")
                    return

                # Check near-duplicate / overlapping refinement within 5.0s
                if time_since_last < 5.0:
                    words_new = set([w for w in new_text.split() if len(w) > 1])
                    words_last = set([w for w in last_text.split() if len(w) > 1])
                    common = words_new.intersection(words_last)
                    smaller_len = min(len(words_new), len(words_last))

                    is_word_overlap = (smaller_len >= 3 and len(common) >= smaller_len * 0.70)
                    is_contained = (new_text in last_text or last_text in new_text) and min(len(new_text), len(last_text)) >= 4

                    if is_word_overlap or is_contained:
                        logger.debug(f"Broadcaster: Updating previous user message with refined transcript: {text}")
                        last_msg["content"] = text
                        last_msg["timestamp"] = time.time()
                        if turn_id:
                            last_msg["turn_id"] = turn_id
                        await self.broadcast("user_transcript", last_msg)
                        return

            self.state["conversation"].append(entry)
            self.state["metrics"]["total_turns"] += 1
            # Keep history manageable
            if len(self.state["conversation"]) > 50:
                self.state["conversation"] = self.state["conversation"][-50:]

        await self.broadcast("user_transcript", entry)

    async def notify_agent_response(self, text: str, mark_id: Optional[str] = None, is_final: bool = False, turn_id: Optional[str] = None):
        entry = {
            "role": "assistant",
            "content": text,
            "mark_id": mark_id,
            "turn_id": turn_id,
            "is_final": is_final,
            "timestamp": time.time()
        }
        if is_final:
            if mark_id and any(m.get("mark_id") == mark_id for m in self.state["conversation"]):
                return
            if turn_id and any(m.get("turn_id") == turn_id and m.get("role") == "assistant" for m in self.state["conversation"]):
                return
            self.state["conversation"].append(entry)
            if len(self.state["conversation"]) > 50:
                self.state["conversation"] = self.state["conversation"][-50:]

        await self.broadcast("agent_response", entry)
        await self.broadcast("transcript", entry)

    async def clear_conversation(self):
        """
        Completely clear active conversation history, current tool state,
        last RAG snippets, turn metrics, and active unpersisted booking state.
        Preserves agent status and database bookings.
        """
        async with self._lock:
            self.state["conversation"] = []
            self.state["current_tool"] = None
            self.state["last_rag"] = None
            self.state["active_booking"] = None
            if "metrics" in self.state:
                self.state["metrics"]["total_turns"] = 0
            if self.state.get("active_call"):
                self.state["session_state"] = "LISTENING"
            else:
                self.state["session_state"] = "IDLE"

        await self.broadcast("conversation_cleared", {
            "conversation": [],
            "current_tool": None,
            "last_rag": None,
            "session_state": self.state["session_state"]
        })

    def clear_conversation_sync(self):
        """Synchronous version for test teardown and immediate state reset."""
        self.state["conversation"] = []
        self.state["current_tool"] = None
        self.state["last_rag"] = None
        self.state["active_booking"] = None
        if "metrics" in self.state:
            self.state["metrics"]["total_turns"] = 0
        if self.state.get("active_call"):
            self.state["session_state"] = "LISTENING"
        else:
            self.state["session_state"] = "IDLE"


    async def notify_barge_in(self, latency_ms: float):
        barge_in_data = {
            "latency_ms": round(latency_ms, 1),
            "timestamp": time.time()
        }
        self.state["last_barge_in"] = barge_in_data
        self.state["session_state"] = "BARGED_IN"
        self.state["metrics"]["barge_in_count"] += 1
        await self.broadcast("barge_in_detected", barge_in_data)

    async def notify_tool_call(self, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None, status: str = "executing"):
        tool_data = {
            "name": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status,
            "timestamp": time.time()
        }
        self.state["current_tool"] = tool_data
        self.state["metrics"]["total_tool_calls"] += 1
        await self.broadcast("tool_executed", tool_data)
        if status == "executing":
            await self.broadcast("tool_call", tool_data)
        elif status == "completed":
            await self.broadcast("tool_result", tool_data)

    async def notify_rag_retrieval(self, query: str, docs: List[Dict[str, Any]]):
        rag_data = {
            "query": query,
            "docs": docs,
            "timestamp": time.time()
        }
        self.state["last_rag"] = rag_data
        await self.broadcast("rag_retrieval", rag_data)

    async def notify_booking_update(self, booking_data: Dict[str, Any]):
        current = self.state.get("active_booking") or {}
        merged = {**current, **booking_data}
        self.state["active_booking"] = merged
        await self.broadcast("booking_updated", merged)
        await self.broadcast("booking_update", merged)


# Global singleton instance
event_broadcaster = EventBroadcaster()
