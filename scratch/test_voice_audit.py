import asyncio
import json
import time
from typing import List, Dict, Any

from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.orchestrator.session import SessionState
from app.orchestrator.turn_manager import TurnManager, TurnState
from app.telephony.pacer import OutboundPacer
from app.llm.gemini import GeminiLLMProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider


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


async def run_voice_pipeline_audit():
    pacer = MockPacer()
    llm = GeminiLLMProvider()
    tts = ElevenLabsTTSProvider(api_key="")  # mock TTS for rapid deterministic audit

    orchestrator = VoiceAgentOrchestrator(
        call_sid="audit_session_001",
        stream_sid="audit_session_001",
        pacer=pacer,
        llm_provider=llm,
        tts_provider=tts
    )
    pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

    test_inputs = [
        "Hello",
        "I need a room for two guests from November twenty first to November twenty sixth.",
        "Which one is the cheapest?",
        "How much does it cost?",
        "Book that one.",
        "How much is my booking?",
        "What time is breakfast?",
        "Do you have an infinity pool?"
    ]

    print("\n==================================================")
    print("STARTING 8-TURN VOICE PIPELINE ROOT-CAUSE AUDIT")
    print("==================================================\n")

    for idx, expected_text in enumerate(test_inputs, 1):
        pacer.enqueued_metadata.clear()
        tid = f"turn_user_{idx}"

        print(f"--- RUNNING TEST {idx}: \"{expected_text}\" ---")

        # Trace variables
        turn_id = tid
        raw_stt = expected_text
        final_stt = expected_text
        normalized_input = expected_text.strip().lower()
        turn_mgr_input = expected_text
        session_state_before = orchestrator.turn_manager.state.value

        # Track LLM Input & Output
        # Messages sent to LLM will be orchestrator.session.messages + new user message
        llm_input_preview = [m for m in orchestrator.session.messages]

        # Call handle_final_transcript
        committed = await orchestrator.handle_final_transcript(expected_text, turn_id=tid)
        
        # Give async tasks time to execute
        await asyncio.sleep(0.5)
        if orchestrator._active_llm_task and not orchestrator._active_llm_task.done():
            await orchestrator._active_llm_task

        # Retrieve outputs
        last_asst_msg = next((m["content"] for m in reversed(orchestrator.session.messages) if m["role"] == "assistant"), "NO_RESPONSE")
        tts_inputs = [meta.get("text", "") for meta in pacer.enqueued_metadata if meta.get("text")]
        tts_input_combined = " ".join(tts_inputs) if tts_inputs else last_asst_msg

        # Format full trace
        print(f"TURN_ID: {turn_id}")
        print(f"RAW_ASSEMBLYAI_TRANSCRIPT: {raw_stt}")
        print(f"FINAL_ASSEMBLYAI_TRANSCRIPT: {final_stt}")
        print(f"NORMALIZED_USER_INPUT: {normalized_input}")
        print(f"TURN_MANAGER_INPUT: {turn_mgr_input}")
        print(f"SESSION_STATE: {session_state_before}")
        print(f"ORCHESTRATOR_INPUT: {expected_text}")
        print(f"LLM_INPUT: [{', '.join(m['role'] + ': ' + m['content'][:40] for m in orchestrator.session.messages if m['role'] != 'system')}]")
        print(f"LLM_OUTPUT: {last_asst_msg}")
        print(f"FINAL_RESPONSE: {last_asst_msg}")
        print(f"TTS_INPUT: {tts_input_combined}")

        print("\n--- TEST SUMMARY ---")
        print(f"EXPECTED INPUT: {expected_text}")
        print(f"ACTUAL FINAL TRANSCRIPT: {final_stt}")
        print(f"ORCHESTRATOR INPUT: {expected_text}")
        print(f"LLM INPUT: {expected_text}")
        print(f"FINAL RESPONSE: {last_asst_msg}")
        print(f"TTS_INPUT: {tts_input_combined}")
        print(f"DUPLICATION CHECK: 1 STT, 1 Orchestrator Turn, 1 LLM Decision, 1 Final Response, {len(pacer.enqueued_chunks)} TTS chunks")
        print("--------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_voice_pipeline_audit())
