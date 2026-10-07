import asyncio
import base64
import json
import time
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.core.logging import logger
from app.core.security import twilio_security
from app.orchestrator.orchestrator import VoiceAgentOrchestrator
from app.stt.base import STTCallback, STTProvider
from app.stt.factory import get_stt_provider
from app.telephony.pacer import OutboundPacer

telephony_router = APIRouter()


@telephony_router.websocket("/ws/media-stream")
async def twilio_media_stream_ws(websocket: WebSocket):
    """
    Twilio Bidirectional Media Streams WebSocket endpoint.
    Handles 'start', 'media' (20ms μ-law frames), 'mark', and 'stop' events.
    Validates HMAC session token when present or required.
    Supports dashboard UI clients via mode=dashboard.
    """
    mode = websocket.query_params.get("mode") or websocket.query_params.get("client")
    if mode == "dashboard":
        await websocket.accept()
        from app.orchestrator.broadcaster import event_broadcaster
        await event_broadcaster.register(websocket)
        logger.info("Dashboard UI client connected to /ws/media-stream")
        try:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    msg = json.loads(raw_text)
                    evt = msg.get("event")
                    if evt == "ping":
                        await websocket.send_text(json.dumps({"event": "pong", "timestamp": time.time()}))
                    elif evt == "subscribe":
                        await websocket.send_text(json.dumps({"event": "snapshot", "data": event_broadcaster.get_snapshot()}))
                    elif evt == "clear_conversation":
                        await event_broadcaster.clear_conversation()
                        await websocket.send_text(json.dumps({"event": "conversation_cleared", "data": event_broadcaster.get_snapshot()}))

                except Exception:
                    pass
        except WebSocketDisconnect:
            logger.info("Dashboard UI client disconnected from /ws/media-stream")
        except Exception as exc:
            logger.debug(f"Dashboard WS error: {exc}")
        finally:
            await event_broadcaster.unregister(websocket)
        return

    token = websocket.query_params.get("token")
    verified_call_sid: Optional[str] = None

    if token:
        verified_call_sid = twilio_security.verify_session_token(token)
        if not verified_call_sid:
            logger.warning("Invalid or expired session token on WebSocket connection.")
            if settings.WEBHOOK_SIGNATURE_VERIFY or settings.ENVIRONMENT == "production":
                await websocket.close(code=1008, reason="Unauthorized Session Token")
                return
    elif settings.WEBHOOK_SIGNATURE_VERIFY or settings.ENVIRONMENT == "production":
        logger.warning("Missing required session token on WebSocket connection in production.")
        await websocket.close(code=1008, reason="Missing Session Token")
        return

    await websocket.accept()
    logger.info("WebSocket connection established with Twilio Media Stream.")

    stream_sid: Optional[str] = None
    call_sid: Optional[str] = None
    orchestrator: Optional[VoiceAgentOrchestrator] = None
    pacer: Optional[OutboundPacer] = None
    stt: Optional[STTProvider] = None

    async def send_to_twilio(message_str: str):
        try:
            await websocket.send_text(message_str)
        except Exception as err:
            logger.debug(f"Error sending to Twilio WS: {err}")

    try:
        while True:
            raw_message = await websocket.receive_text()
            data = json.loads(raw_message)
            event_type = data.get("event")

            if event_type == "connected":
                logger.info(f"Twilio protocol connected: {data.get('protocol')}")

            elif event_type == "start":
                start_info = data.get("start", {})
                stream_sid = data.get("streamSid") or start_info.get("streamSid")
                call_sid = start_info.get("callSid")
                custom_params = start_info.get("customParameters", {})
                caller_num = custom_params.get("callerNumber")
                logger.info(f"Media stream started. StreamSid: {stream_sid}, CallSid: {call_sid}")

                try:
                    from app.orchestrator.broadcaster import event_broadcaster
                    asyncio.create_task(event_broadcaster.notify_call_started(call_sid or "", stream_sid or "", caller_num))
                except Exception:
                    pass

                # Initialize Outbound Pacer
                pacer = OutboundPacer(stream_sid=stream_sid, send_fn=send_to_twilio)
                pacer.start()

                simulated_utterance = custom_params.get("simulated_utterance")
                from app.tts.elevenlabs import ElevenLabsTTSProvider
                simulated_tts = ElevenLabsTTSProvider(api_key="") if simulated_utterance else None

                # Initialize Voice Orchestrator
                orchestrator = VoiceAgentOrchestrator(
                    call_sid=call_sid,
                    stream_sid=stream_sid,
                    pacer=pacer,
                    tts_provider=simulated_tts
                )
                pacer.on_playback_complete = orchestrator.turn_manager.on_tts_finished

                # Initialize Streaming STT
                stt_callbacks = STTCallback(
                    on_interim=orchestrator.handle_interim_transcript,
                    on_final=orchestrator.handle_final_transcript,
                    on_error=lambda err: logger.error(f"STT stream error: {err}")
                )
                stt = get_stt_provider(callbacks=stt_callbacks, simulated_utterance=simulated_utterance)
                try:
                    await stt.connect()
                except Exception as stt_err:
                    logger.error(f"STT provider connection error: {stt_err}", exc_info=True)

                # Dispatch initial spoken welcome greeting safely
                async def safe_greeting():
                    try:
                        await orchestrator.send_initial_greeting()
                    except Exception as greeting_err:
                        logger.error(f"Error delivering initial greeting: {greeting_err}", exc_info=True)

                asyncio.create_task(safe_greeting())

            elif event_type == "media":
                if not orchestrator or not stt:
                    continue

                payload_b64 = data.get("media", {}).get("payload")
                if payload_b64:
                    ulaw_frame = base64.b64decode(payload_b64)
                    # Feed audio to EnergyGate & STT
                    await orchestrator.handle_inbound_audio(ulaw_frame)
                    await stt.send_audio(ulaw_frame)

            elif event_type == "mark":
                mark_name = data.get("mark", {}).get("name")
                if mark_name and pacer:
                    pacer.handle_mark_ack(mark_name)

            elif event_type == "stop":
                logger.info(f"Twilio stream stop event received for stream: {stream_sid}")
                break

    except WebSocketDisconnect:
        logger.info(f"Twilio Media Stream disconnected for stream: {stream_sid}")
    except Exception as exc:
        logger.error(f"Exception in media stream loop: {exc}", exc_info=True)
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
        logger.info(f"Cleaned up telephony session for stream: {stream_sid}")
