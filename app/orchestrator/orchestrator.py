import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from app.audio.energy_gate import EnergyGate
from app.core.config import settings
from app.core.logging import logger
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiLLMProvider
from app.llm.openai import OpenAILLMProvider
from app.orchestrator.session import SessionState
from app.orchestrator.turn_manager import TurnManager, TurnState
from app.rag.prefetch import prefetch_cache
from app.rag.retriever import get_retriever
from app.telephony.pacer import OutboundPacer
from app.tools.tool_registry import tool_registry
from app.tts.base import TTSProvider
from app.tts.chunker import StreamingSentenceChunker
from app.tts.elevenlabs import ElevenLabsTTSProvider
from app.db.session import AsyncSessionLocal


class VoiceAgentOrchestrator:
    """
    Central real-time voice pipeline orchestrator.
    Binds STT, EnergyGate, TurnManager, LLM with 6 tools, TTS, and Outbound Pacer.
    Coordinates sub-200ms barge-in cancellation and mark-based transcript truncation.
    """

    def __init__(
        self,
        call_sid: str,
        stream_sid: str,
        pacer: OutboundPacer,
        llm_provider: Optional[LLMProvider] = None,
        tts_provider: Optional[TTSProvider] = None
    ):
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.pacer = pacer
        if llm_provider:
            self.llm = llm_provider
        elif settings.LLM_PROVIDER in ("gemini", "google"):
            self.llm = GeminiLLMProvider()
        else:
            self.llm = OpenAILLMProvider()
        self.tts = tts_provider or ElevenLabsTTSProvider()

        self.session = SessionState(call_sid=call_sid, stream_sid=stream_sid)

        # Interruption energy gate
        self.energy_gate = EnergyGate(
            base_threshold=settings.RMS_ENERGY_THRESHOLD,
            consecutive_frames=settings.VAD_INTERRUPTION_FRAMES,
            on_interruption=self._on_energy_interruption
        )

        # Turn coordinator
        self.turn_manager = TurnManager(
            on_barge_in=self._execute_barge_in,
            on_user_turn_ready=self._process_user_turn
        )
        self.pacer.on_playback_complete = self.turn_manager.on_tts_finished

        # Active background tasks for cancellation
        self._active_llm_task: Optional[asyncio.Task] = None
        self._active_tts_task: Optional[asyncio.Task] = None
        self._speculative_task: Optional[asyncio.Task] = None

    async def reset_conversation(self):
        """
        Completely reset conversation state: cancels any running LLM/TTS generation,
        flushes audio pacer, resets SessionState (keeping only SYSTEM_PROMPT),
        resets TurnManager to LISTENING, and resets EnergyGate counters.
        """
        logger.info(f"Orchestrator: Resetting conversation for call {self.call_sid}")
        if self._active_llm_task and not self._active_llm_task.done():
            self._active_llm_task.cancel()
        if self._active_tts_task and not self._active_tts_task.done():
            self._active_tts_task.cancel()
        if self._speculative_task and not self._speculative_task.done():
            self._speculative_task.cancel()

        if hasattr(self.pacer, "reset"):
            try:
                await self.pacer.reset()
            except Exception as e:
                logger.debug(f"Pacer reset exception: {e}")
        elif hasattr(self.pacer, "flush"):
            try:
                await self.pacer.flush()
            except Exception as e:
                logger.debug(f"Pacer flush exception: {e}")

        self.session.reset_conversation()
        self.turn_manager.reset()
        self.energy_gate.reset()

    def _on_energy_interruption(self):

        """Dispatched synchronously from EnergyGate when voice threshold is crossed."""
        if self.turn_manager.is_speaking():
            asyncio.create_task(self.turn_manager.trigger_barge_in())

    async def _execute_barge_in(self):
        """
        Sub-200ms Barge-in Interruption Sequence:
        1. Cancel active LLM streaming task.
        2. Cancel active TTS synthesis task.
        3. Flush outbound audio pacer queue & send Twilio CLEAR event.
        4. Read last acknowledged Twilio MARK.
        5. Truncate assistant transcript in conversation session state.
        6. Return to LISTENING state.
        """
        start_t = time.monotonic()
        logger.info(f"Orchestrator: Executing BARGE-IN for call {self.call_sid}")

        # 1. Cancel LLM streaming
        if self._active_llm_task and not self._active_llm_task.done():
            self._active_llm_task.cancel()

        # 2. Cancel TTS synthesis
        if self._active_tts_task and not self._active_tts_task.done():
            self._active_tts_task.cancel()

        # 3. Flush pacer queue & send Twilio CLEAR
        await self.pacer.flush()

        # 4 & 5. Mark tracking & transcript truncation
        last_acked_mark, _ = self.pacer.get_last_acked()
        self.session.truncate_on_barge_in(last_acked_mark)

        # 6. Reset TurnManager state to LISTENING so next user speech is immediately accepted
        from app.orchestrator.turn_manager import TurnState
        self.turn_manager.set_state(TurnState.LISTENING)
        self.turn_manager.last_committed_time = 0.0

        elapsed_ms = (time.monotonic() - start_t) * 1000
        logger.info(f"Orchestrator: Barge-in interruption completed in {elapsed_ms:.1f}ms")
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            asyncio.create_task(event_broadcaster.notify_barge_in(elapsed_ms))
        except Exception:
            pass

    async def send_initial_greeting(self, greeting_text: Optional[str] = None):
        """
        Deliver initial spoken welcome greeting upon call establishment.
        Synthesizes greeting audio and streams it through the outbound pacer.
        Strictly delivered only once per session.
        """
        if self.session.has_greeted:
            logger.info("Orchestrator: Initial greeting already delivered; skipping duplicate greeting.")
            return
        self.session.has_greeted = True

        text = greeting_text or "Welcome to Azure Paradise Resort! How may I assist you with your stay today?"
        logger.info(f"Orchestrator: Delivering initial call greeting: '{text}'")
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            asyncio.create_task(event_broadcaster.notify_agent_response(text, is_final=True))
        except Exception:
            pass
        self.session.start_assistant_turn()
        self.pacer.start_turn()
        await self._synthesize_and_enqueue(text)
        self.pacer.mark_turn_end()
        self.session.complete_assistant_turn(text)

    async def handle_inbound_audio(self, ulaw_frame: bytes):
        """Process an incoming 20ms μ-law audio frame."""
        # Process through EnergyGate
        is_speaking = self.turn_manager.is_speaking()
        self.energy_gate.process_frame(ulaw_frame, is_assistant_speaking=is_speaking)

    async def handle_interim_transcript(self, text: str, turn_id: Optional[str] = None):
        """
        Trigger speculative RAG prefetch when interim transcript shows inquiry patterns.
        """
        tid = self.turn_manager.handle_user_speech_partial(text, turn_id)
        if tid:
            try:
                from app.orchestrator.broadcaster import event_broadcaster
                asyncio.create_task(event_broadcaster.notify_user_transcript(text, is_final=False, turn_id=tid))
            except Exception:
                pass
        if len(text.split()) >= 3 and not self._speculative_task:
            self._speculative_task = asyncio.create_task(self._speculative_rag_prefetch(text))

    async def _speculative_rag_prefetch(self, text: str):
        """Background speculative prefetch into TTL cache."""
        try:
            logger.debug(f"Speculative RAG: Probing prefetch for '{text}'")
            retriever = get_retriever()
            docs = await retriever.aretrieve(text, top_k=settings.RAG_TOP_K)
            formatted = [{"content": d.page_content, "source": d.metadata.get("source", "kb")} for d in docs]
            await prefetch_cache.set(text, formatted)
        except Exception as e:
            logger.debug(f"Speculative prefetch error: {e}")
        finally:
            self._speculative_task = None

    async def handle_final_transcript(self, text: str, turn_id: Optional[str] = None) -> bool:
        """Process finalized customer speech turn, ensuring exactly one commit."""
        committed = await self.turn_manager.handle_user_speech_final(text, turn_id)
        if committed:
            tid = self.turn_manager.last_committed_turn_id or turn_id
            try:
                from app.orchestrator.broadcaster import event_broadcaster
                asyncio.create_task(event_broadcaster.notify_user_transcript(text, is_final=True, turn_id=tid))
            except Exception:
                pass
        return committed

    async def _process_user_turn(self, user_text: str, turn_id: Optional[str] = None):
        """Orchestrate LLM streaming response, function execution, and TTS chunking."""
        tid = turn_id or f"turn_{int(time.monotonic() * 1000)}"
        logger.info(f"Orchestrator: Processing user turn [{tid}]: '{user_text}'")
        from app.utils.date_parser import parse_date_range
        p_ci, p_co, p_err = parse_date_range(user_text)
        self._current_user_text = user_text
        self._current_turn_id = tid
        self._turn_parsed_ci = p_ci
        self._turn_parsed_co = p_co
        self._turn_parsed_err = p_err
        self._turn_last_tool_name = None
        self._turn_last_tool_args = None
        self._turn_last_tool_result = None

        self.session.add_user_message(user_text)

        self.session.start_assistant_turn()
        self.pacer.start_turn()

        self._active_llm_task = asyncio.create_task(self._stream_llm_and_tts(turn_id=tid))
        try:
            await self._active_llm_task
        except asyncio.CancelledError:
            logger.info("Orchestrator: LLM task cancelled by barge-in.")
        except Exception as exc:
            logger.error(f"Orchestrator turn error: {exc}", exc_info=True)

    async def _stream_llm_and_tts(self, turn_id: Optional[str] = None):
        """Streams LLM tokens, executes tool calls if requested, and pipes sentences to TTS."""
        tid = turn_id or "unknown"
        chunker = StreamingSentenceChunker(min_chunk_words=3)
        tools = tool_registry.get_tool_definitions()

        full_response_text = []
        pending_tool_calls: List[Dict[str, Any]] = []

        try:
            stream = self.llm.stream_chat(self.session.messages, tools=tools)

            async for event in stream:
                if event["type"] == "token":
                    token = event["content"]
                    full_response_text.append(token)
                    sentences = chunker.feed(token)
                    for sentence in sentences:
                        await self._synthesize_and_enqueue(sentence)

                elif event["type"] == "tool_call":
                    pending_tool_calls.append(event)

            # Flush any remaining tokens in chunker
            remaining = chunker.flush()
            if remaining:
                await self._synthesize_and_enqueue(remaining)

            # If tool calls were triggered, execute them and stream LLM follow-up response
            last_tool_result = None
            if pending_tool_calls:
                async with AsyncSessionLocal() as turn_db_session:
                    for tc in pending_tool_calls:
                        tool_name = tc["name"]
                        arguments = dict(tc.get("arguments") or {})
                        logger.info(f"LLM requested tool call: {tool_name} with args {arguments}")

                        # Contextual propagation: ensure active dates/rooms/guests from session state
                        # are preserved even if the LLM omitted them in function call arguments
                        if tool_name in ("check_availability", "calculate_price", "create_booking"):
                            if getattr(self, '_turn_parsed_ci', None) and getattr(self, '_turn_parsed_co', None):
                                arguments["check_in"] = self._turn_parsed_ci
                                arguments["check_out"] = self._turn_parsed_co
                            else:
                                if not arguments.get("check_in") and self.session.check_in:
                                    arguments["check_in"] = self.session.check_in
                                if not arguments.get("check_out") and self.session.check_out:
                                    arguments["check_out"] = self.session.check_out

                        if tool_name in ("check_availability", "create_booking"):
                            if not arguments.get("guests") and self.session.guests:
                                arguments["guests"] = self.session.guests

                        if tool_name in ("calculate_price", "create_booking"):
                            user_lower = (getattr(self, '_current_user_text', '') or "").lower()
                            user_named_room = any(k in user_lower for k in [
                                "villa", "suite", "bungalow", "oceanfront", "deluxe", "presidential", "family", "premium"
                            ])
                            # If caller did not explicitly name another room in this turn,
                            # lock room_id to current selected or confirmed room
                            if not user_named_room and self.session.selected_room_id:
                                arguments["room_id"] = self.session.selected_room_id
                            elif not arguments.get("room_id") and self.session.selected_room_id:
                                arguments["room_id"] = self.session.selected_room_id

                        if tool_name == "calculate_price":
                            if self.session.confirmed_booking_id and not arguments.get("booking_id"):
                                arguments["booking_id"] = self.session.confirmed_booking_id
                            if not arguments.get("room_id") and self.session.selected_room_id:
                                arguments["room_id"] = self.session.selected_room_id

                        if tool_name == "create_booking":
                            if not arguments.get("guest_name"):
                                arguments["guest_name"] = self.session.guest_name or "Valued Guest"
                            if not arguments.get("guest_email"):
                                arguments["guest_email"] = self.session.guest_email or "guest@azureparadise-resort.com"
                            if not arguments.get("guest_phone"):
                                arguments["guest_phone"] = self.session.guest_phone or "+1-808-555-0100"
                            if not arguments.get("total_price") or float(arguments.get("total_price", 0)) <= 0:
                                target_rid = arguments.get("room_id") or self.session.selected_room_id or "bungalow-garden-301"
                                target_ci = arguments.get("check_in") or self.session.check_in
                                target_co = arguments.get("check_out") or self.session.check_out
                                if target_ci and target_co:
                                    calc_res = await tool_registry.execute_tool(
                                        "calculate_price",
                                        {"room_id": target_rid, "check_in": target_ci, "check_out": target_co},
                                        db_session=turn_db_session
                                    )
                                    arguments["total_price"] = calc_res.get("total_price", 1000.0)

                        tool_result = await tool_registry.execute_tool(tool_name, arguments, db_session=turn_db_session)
                        last_tool_result = tool_result
                        self._turn_last_tool_name = tool_name
                        self._turn_last_tool_args = arguments
                        self._turn_last_tool_result = tool_result
                        self.session.update_context_from_tool(tool_name, arguments, tool_result)

                        try:
                            from app.orchestrator.broadcaster import event_broadcaster
                            asyncio.create_task(event_broadcaster.notify_tool_call(tool_name, arguments, tool_result, "completed"))
                            if isinstance(tool_result, dict) and ("booking_id" in tool_result or "pending_token" in tool_result or "booking_code" in tool_result or "total_price" in tool_result):
                                asyncio.create_task(event_broadcaster.notify_booking_update(tool_result))
                        except Exception:
                            pass

                        # Record tool response in session messages
                        self.session.messages.append({
                            "role": "function",
                            "name": tool_name,
                            "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                        })

                    # Commit turn session so database mutations (create_booking, save_booking) persist
                    try:
                        await turn_db_session.commit()
                    except Exception as commit_err:
                        logger.error(f"Error committing turn_db_session: {commit_err}")

                # Stream LLM follow-up response based on the actual tool result
                followup_stream = self.llm.stream_chat(self.session.messages, tools=None)
                async for event in followup_stream:
                    if event["type"] == "token":
                        token = event["content"]
                        full_response_text.append(token)
                        sentences = chunker.feed(token)
                        for sentence in sentences:
                            await self._synthesize_and_enqueue(sentence, tool_result=last_tool_result)

                remaining = chunker.flush()
                if remaining:
                    await self._synthesize_and_enqueue(remaining, tool_result=last_tool_result)

            # Fallback if no text tokens were produced after tool execution
            if not full_response_text and last_tool_result and last_tool_result.get("spoken_hint"):
                fallback_hint = last_tool_result["spoken_hint"]
                await self._synthesize_and_enqueue(fallback_hint, tool_result=last_tool_result)
                full_response_text.append(fallback_hint)

            complete_text = "".join(full_response_text).strip()
            if complete_text:
                self.session.complete_assistant_turn(complete_text)

                debug_block = (
                    f"[VOICE-DEBUG]\n"
                    f"TURN_ID={tid}\n"
                    f"RAW_UTTERANCE={getattr(self, '_current_user_text', 'None')}\n"
                    f"PARSED_CHECK_IN={getattr(self, '_turn_parsed_ci', None) or 'None'}\n"
                    f"PARSED_CHECK_OUT={getattr(self, '_turn_parsed_co', None) or 'None'}\n"
                    f"PARSED_GUESTS={self.session.guests}\n"
                    f"SESSION_CHECK_IN={self.session.check_in or 'None'}\n"
                    f"SESSION_CHECK_OUT={self.session.check_out or 'None'}\n"
                    f"SESSION_GUESTS={self.session.guests}\n"
                    f"SESSION_SELECTED_ROOM={self.session.selected_room_id or 'None'}\n"
                    f"SESSION_AVAILABLE_ROOMS={[r.get('room_id') for r in self.session.available_rooms]}\n"
                    f"CURRENT_INTENT={self.session.current_intent or 'None'}\n"
                    f"LLM_PROVIDER={self.llm.__class__.__name__}\n"
                    f"SIMULATION_MODE={getattr(self.llm, 'api_key', None) is None or getattr(self.llm, 'client', None) is None}\n"
                    f"LLM_CONTEXT={self.session.messages[0]['content'] if self.session.messages else 'None'}\n"
                    f"TOOL_NAME={getattr(self, '_turn_last_tool_name', None) or 'None'}\n"
                    f"TOOL_ARGS={getattr(self, '_turn_last_tool_args', None) or 'None'}\n"
                    f"TOOL_RESULT={getattr(self, '_turn_last_tool_result', None) or 'None'}\n"
                    f"FINAL_RESPONSE={complete_text}"
                )
                print(f"\n{debug_block}\n", flush=True)
                logger.info(f"\n{debug_block}")

                try:
                    from app.orchestrator.broadcaster import event_broadcaster
                    asyncio.create_task(event_broadcaster.notify_agent_response(complete_text, is_final=True))
                except Exception:
                    pass

            # Mark turn completion strictly when generation completes normally
            self.pacer.mark_turn_end()

        except asyncio.CancelledError:
            logger.info("Orchestrator: LLM streaming cancelled by barge-in; skipping turn_end.")
            raise
        except Exception as exc:
            logger.error(f"Orchestrator turn error: {exc}", exc_info=True)
            self.pacer.mark_turn_end()

    async def _synthesize_and_enqueue(self, sentence: str, tool_result: Optional[dict] = None):
        """Synthesize sentence chunk and push to outbound pacer."""
        if not sentence.strip():
            return

        self.turn_manager.on_tts_started()
        mark_id = f"sent_{int(time.monotonic() * 1000)}"
        self.session.record_sentence_chunk(sentence, mark_id)

        meta = {"mark_id": mark_id, "text": sentence}
        if tool_result:
            meta["tool_result"] = tool_result

        try:
            async for audio_chunk in self.tts.stream_audio(sentence):
                await self.pacer.enqueue_audio(audio_chunk, metadata=meta)
        except asyncio.CancelledError:
            logger.info("TTS streaming task cancelled.")
            raise
        except Exception as exc:
            logger.error(f"Error during TTS synthesis: {exc}")
