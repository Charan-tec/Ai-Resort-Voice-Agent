import asyncio
import json
import re
from datetime import date, datetime
from typing import Optional

from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.orchestrator.session import SessionState
from app.orchestrator.turn_manager import TurnManager
from app.telephony.pacer import OutboundPacer
from app.llm.gemini import GeminiLLMProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider
from app.utils.date_parser import parse_date_range, get_reference_date
from app.tools.availability import check_availability
from app.db.session import AsyncSessionLocal


class MockPacer(OutboundPacer):
    def __init__(self):
        self.enqueued_chunks = []
        self.enqueued_metadata = []
        self.on_playback_complete = None

    def start_turn(self):
        pass

    def mark_turn_end(self, turn_id=None):
        if self.on_playback_complete:
            self.on_playback_complete()

    async def enqueue_audio(self, ulaw_data: bytes, metadata=None):
        self.enqueued_chunks.append(ulaw_data)
        if metadata:
            self.enqueued_metadata.append(metadata)

    def get_last_acked(self):
        return None, None

    async def flush(self):
        self.enqueued_chunks.clear()
        self.enqueued_metadata.clear()

    async def reset(self):
        await self.flush()


async def run_date_availability_audit():
    ref_date = date(2026, 10, 7)
    
    test_cases = [
        "I need a room for two guests from November 21 to November 25",
        "I need a room for two guests from January 10 to January 15",
        "I need a room for two guests from November 21 2027 to November 25 2027",
        "I need a room for two guests from November 21 2030 to November 25 2030",
        "I need a room for two guests from December 28 2027 to January 3 2028",
        "I need a room for two guests from February 28 2028 to March 2 2028",
        "I need a room for two guests from February 29 2027 to March 2 2027",
        "I need a room for two guests from November 25 to November 21",
        "I need a room for two guests from November 21 2030 to November 25 2030",
        "What rooms are available from November 21 2029 to November 25 2029",
    ]

    pacer = MockPacer()
    llm = GeminiLLMProvider()
    tts = ElevenLabsTTSProvider(api_key="")

    orchestrator = VoiceAgentOrchestrator(
        call_sid="date_audit_001",
        stream_sid="date_audit_001",
        pacer=pacer,
        llm_provider=llm,
        tts_provider=tts
    )
    pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

    print("\n==================================================")
    print("STARTING DATE -> AVAILABILITY PIPELINE AUDIT")
    print("==================================================\n")

    for idx, raw_transcript in enumerate(test_cases, 1):
        tid = f"turn_date_{idx}"
        pacer.enqueued_metadata.clear()

        # Step 1: Normalized input
        normalized_input = raw_transcript.strip().lower()

        # Step 2: Date Parser & Reason
        p_ci, p_co, p_err = parse_date_range(raw_transcript, reference_date=ref_date)
        
        # Determine reason
        if p_err:
            reason = f"Rejected: {p_err}"
        elif re.search(r'\b(202[6-9]|20[3-9]\d)\b', raw_transcript):
            reason = "Explicit year specified by guest in utterance"
        else:
            # Check implicit logic
            m1_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', normalized_input)
            if m1_match and m1_match.group(1) in ("january", "february", "march", "april", "may", "june", "july", "august", "september"):
                reason = "Implicit year: Month already elapsed in 2026, rolled over dynamically to next calendar year"
            else:
                reason = "Implicit year: Month is in current year upcoming future (2026)"

        # Guest extraction
        p_guests = 2
        for w, val in [("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5), ("six", 6)]:
            if f"{w} guest" in normalized_input or f"party of {w}" in normalized_input or f"for {w}" in normalized_input:
                p_guests = val
                break

        # Step 3: Handle through orchestrator
        committed = await orchestrator.handle_final_transcript(raw_transcript, turn_id=tid)
        await asyncio.sleep(0.4)
        if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
            await orchestrator._active_llm_task

        session_ci = orchestrator.session.check_in
        session_co = orchestrator.session.check_out

        tool_ci = orchestrator._turn_last_tool_args.get("check_in") if orchestrator._turn_last_tool_args else "NONE"
        tool_co = orchestrator._turn_last_tool_args.get("check_out") if orchestrator._turn_last_tool_args else "NONE"
        tool_guests = orchestrator._turn_last_tool_args.get("guests") if orchestrator._turn_last_tool_args else "NONE"
        db_query_dates = f"[{tool_ci}, {tool_co})" if tool_ci != "NONE" else "NO_DB_QUERY (REJECTED_BEFORE_QUERY)"

        tool_res = orchestrator._turn_last_tool_result
        if tool_res:
            tool_res_summary = f"ok={tool_res.get('ok')}, available={tool_res.get('available')}, count={tool_res.get('count')}, rooms={[r['name'] for r in tool_res.get('available_rooms', [])]}"
        else:
            tool_res_summary = f"REJECTED: {p_err or 'No tool called'}"

        last_asst_msg = next((m["content"] for m in reversed(orchestrator.session.messages) if m["role"] == "assistant"), "NO_RESPONSE")

        print(f"--- TEST CASE {idx} ---")
        print(f"RAW_TRANSCRIPT: {raw_transcript}")
        print(f"NORMALIZED_INPUT: {normalized_input}")
        print(f"PARSED_CHECK_IN: {p_ci or 'NONE'}")
        print(f"PARSED_CHECK_OUT: {p_co or 'NONE'}")
        print(f"PARSED_GUESTS: {p_guests}")
        print(f"DATE_RESOLUTION_REASON: {reason}")
        print(f"SESSION_CHECK_IN: {session_ci or 'NONE'}")
        print(f"SESSION_CHECK_OUT: {session_co or 'NONE'}")
        print(f"TOOL_CHECK_IN: {tool_ci}")
        print(f"TOOL_CHECK_OUT: {tool_co}")
        print(f"TOOL_GUESTS: {tool_guests}")
        print(f"DATABASE_QUERY_DATES: {db_query_dates}")
        print(f"TOOL_RESULT: {tool_res_summary}")
        print(f"FINAL_RESPONSE: {last_asst_msg}")
        print("--------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_date_availability_audit())
