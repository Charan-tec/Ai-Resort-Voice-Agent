import asyncio
import json
import time
from typing import Optional
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.core.logging import logger
from app.llm.gemini import GeminiLLMProvider
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.stt.base import STTCallback, STTProvider
from app.stt.factory import get_stt_provider
from app.telephony.exotel_adapter import ExotelMediaAdapter, ExotelOutboundPacer
from app.tts.elevenlabs import ElevenLabsTTSProvider

exotel_router = APIRouter()


@exotel_router.post("/ws/exotel-media", tags=["Exotel Telephony"])
async def exotel_media_post(request: Request):
    """
    Exotel AgentStream HTTP webhook / call-connect handshake endpoint.
    Accepts incoming call events from Exotel applets/flows and returns
    bidirectional stream connection instructions.
    """
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        data = {}

    call_sid = data.get("CallSid") or data.get("call_sid") or "exotel_call"
    from_num = data.get("From") or data.get("from") or "Unknown"
    logger.info(f"Exotel AgentStream HTTP POST received from {from_num} (CallSid: {call_sid})")

    # Determine stream URL
    stream_url = settings.effective_exotel_stream_url
    forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host")
    forwarded_proto = request.headers.get("X-Forwarded-Proto") or "https"
    if "example.com" in stream_url and forwarded_host and not any(h in forwarded_host.lower() for h in ("localhost", "127.0.0.1")):
        ws_proto = "wss" if forwarded_proto == "https" else "ws"
        stream_url = f"{ws_proto}://{forwarded_host}/ws/exotel-media"

    accept = request.headers.get("accept", "")
    if "application/xml" in accept or "text/xml" in accept:
        xml_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<Response>\n'
            f'  <Connect>\n'
            f'    <Stream url="{stream_url}" type="bidirectional" format="pcm_8000"/>\n'
            f'  </Connect>\n'
            f'</Response>'
        )
        return Response(content=xml_content, media_type="application/xml")

    return {
        "status": "success",
        "StreamUrl": stream_url,
        "StreamType": "bidirectional",
        "AudioFormat": "pcm_8000",
        "CallSid": call_sid
    }


@exotel_router.get("/ws/exotel-media", tags=["Exotel Telephony"])
async def exotel_media_get():
    """Exotel AgentStream information and readiness probe."""
    return {
        "status": "ready",
        "service": "exotel-agentstream",
        "stream_url": settings.effective_exotel_stream_url,
        "audio_format": "8kHz mono linear16 PCM",
        "configured": settings.is_exotel_configured
    }


@exotel_router.websocket("/ws/exotel-media")
async def exotel_media_stream_ws(websocket: WebSocket):
    """
    Exotel Bidirectional AgentStream WebSocket endpoint.
    Handles 'connected', 'start', 'media' (8kHz mono linear16 PCM), 'mark', 'clear', and 'stop' events.

    Routes audio through:
    Exotel -> /ws/exotel-media -> ExotelMediaAdapter -> AssemblyAI STT ->
    TurnManager / Orchestrator -> Gemini LLM + Tools + RAG + Postgres ->
    ElevenLabs TTS -> ExotelOutboundPacer (8kHz PCM16) -> Exotel -> Caller.
    """
    await websocket.accept()
    logger.info("WebSocket connection established with Exotel AgentStream.")

    stream_sid: Optional[str] = None
    call_sid: Optional[str] = None
    orchestrator: Optional[VoiceAgentOrchestrator] = None
    pacer: Optional[ExotelOutboundPacer] = None
    adapter: Optional[ExotelMediaAdapter] = None
    stt: Optional[STTProvider] = None

    async def send_to_exotel(message_str: str):
        try:
            await websocket.send_text(message_str)
        except Exception as err:
            logger.debug(f"Error sending to Exotel WS: {err}")

    try:
        while True:
            raw_message = await websocket.receive_text()
            data = json.loads(raw_message)
            event_type = data.get("event")

            if event_type == "connected":
                protocol_info = data.get("protocol") or "AgentStream"
                logger.info(f"Exotel AgentStream protocol connected: {protocol_info}")

            elif event_type == "start":
                start_info = data.get("start", {})
                stream_sid = (
                    data.get("stream_sid")
                    or data.get("streamSid")
                    or start_info.get("stream_sid")
                    or start_info.get("streamSid")
                    or "exotel_stream"
                )
                call_sid = (
                    start_info.get("call_sid")
                    or start_info.get("callSid")
                    or data.get("call_sid")
                    or data.get("callSid")
                    or "exotel_call"
                )
                custom_params = start_info.get("custom_parameters") or start_info.get("customParameters") or {}
                caller_num = (
                    start_info.get("from")
                    or start_info.get("From")
                    or custom_params.get("callerNumber")
                    or custom_params.get("caller_number")
                    or "Unknown"
                )
                logger.info(f"Exotel AgentStream started. StreamSid: {stream_sid}, CallSid: {call_sid}, Caller: {caller_num}")

                try:
                    from app.orchestrator.broadcaster import event_broadcaster
                    asyncio.create_task(event_broadcaster.notify_call_started(call_sid or "", stream_sid or "", caller_num))
                except Exception:
                    pass

                # Initialize Exotel Outbound Pacer (8kHz mono linear16 PCM, 320 bytes / 20ms)
                pacer = ExotelOutboundPacer(stream_sid=stream_sid, send_fn=send_to_exotel)
                pacer.start()

                # Initialize Exotel Media Adapter
                adapter = ExotelMediaAdapter(stream_sid=stream_sid, pacer=pacer)

                simulated_utterance = custom_params.get("simulated_utterance")
                simulated_tts = ElevenLabsTTSProvider(api_key="") if simulated_utterance else None

                # Gemini LLM Provider (Flash / streaming)
                gemini_llm = GeminiLLMProvider() if (settings.LLM_PROVIDER in ("gemini", "google") or settings.effective_gemini_api_key) else None

                # Initialize Voice Orchestrator
                orchestrator = VoiceAgentOrchestrator(
                    call_sid=call_sid,
                    stream_sid=stream_sid,
                    pacer=pacer,
                    llm_provider=gemini_llm,
                    tts_provider=simulated_tts or ElevenLabsTTSProvider()
                )
                pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

                # Initialize Streaming STT (AssemblyAI v3)
                stt_callbacks = STTCallback(
                    on_interim=orchestrator.handle_interim_transcript,
                    on_final=orchestrator.handle_final_transcript,
                    on_error=lambda err: logger.error(f"Exotel STT stream error: {err}")
                )
                stt = get_stt_provider(callbacks=stt_callbacks, simulated_utterance=simulated_utterance)
                adapter.set_pipeline_components(orchestrator=orchestrator, stt=stt)

                try:
                    await stt.connect()
                except Exception as stt_err:
                    logger.error(f"Exotel STT provider connection error: {stt_err}", exc_info=True)

                # Dispatch spoken welcome greeting
                async def safe_greeting():
                    try:
                        await orchestrator.send_initial_greeting()
                    except Exception as greeting_err:
                        logger.error(f"Error delivering Exotel initial greeting: {greeting_err}", exc_info=True)

                asyncio.create_task(safe_greeting())

            elif event_type == "media":
                if not adapter:
                    continue

                media_info = data.get("media", {})
                payload_b64 = media_info.get("payload")
                if payload_b64:
                    await adapter.handle_inbound_media_payload(payload_b64)

            elif event_type == "mark":
                mark_info = data.get("mark", {})
                if adapter:
                    adapter.handle_mark_event(mark_info)

            elif event_type == "clear":
                if adapter:
                    adapter.handle_clear_event()

            elif event_type == "stop":
                logger.info(f"Exotel AgentStream stop event received for stream: {stream_sid}")
                break

    except WebSocketDisconnect:
        logger.info(f"Exotel AgentStream WebSocket disconnected for stream: {stream_sid}")
    except Exception as exc:
        logger.error(f"Exception in Exotel AgentStream loop: {exc}", exc_info=True)
    finally:
        # Graceful cleanup
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            asyncio.create_task(event_broadcaster.notify_call_ended(call_sid or "", stream_sid or ""))
        except Exception:
            pass
        if pacer:
            await pacer.stop()
        if stt:
            await stt.close()
        logger.info(f"Cleaned up Exotel AgentStream session for stream: {stream_sid}")
