import asyncio
import inspect
import json
from typing import Optional
import websockets
from app.core.config import settings
from app.core.logging import logger
from app.stt.base import STTCallback, STTProvider
from app.telephony.codecs import calculate_rms, ulaw_to_pcm


class AssemblyAISTTProvider(STTProvider):
    """
    Streaming Speech-to-Text provider using the official AssemblyAI v3 WebSocket API.
    Streams 8kHz μ-law audio frames directly via WebSockets, receiving low-latency
    turn-based interim and final transcripts.

    When an API key is not present or when operating in simulation, gracefully
    falls back to offline/mock energy-gated speech endpointing for local testing.
    """

    def __init__(
        self,
        callbacks: STTCallback,
        api_key: Optional[str] = None,
        simulated_utterance: Optional[str] = None,
        sample_rate: int = 8000,
        speech_model: Optional[str] = None
    ):
        super().__init__(callbacks)
        self.api_key = api_key if api_key is not None else settings.effective_assemblyai_api_key
        self.simulated_utterance = simulated_utterance
        self.sample_rate = sample_rate
        self.speech_model = speech_model or getattr(settings, "STT_MODEL", "universal-streaming-english")
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._closed = False

        # Transcript deduplication state
        self._last_interim_transcript: Optional[str] = None
        self._last_final_transcript: Optional[str] = None

        # Offline / Mock simulation state
        self._speech_frame_count = 0
        self._silence_frame_count = 0

        # Audio chunk buffer for AssemblyAI 50ms-1000ms duration requirement
        self._audio_buffer = bytearray()

    async def connect(self):
        """Establish connection to AssemblyAI v3 Streaming WebSocket API."""
        if not self.api_key or self.simulated_utterance:
            if self.simulated_utterance:
                logger.info(f"AssemblyAI operating in simulation mode with utterance: '{self.simulated_utterance}'")
            else:
                logger.warning("AssemblyAI API key not configured; operating in offline/mock STT mode.")
            self.is_connected = True
            return

        VALID_MODELS = {
            "universal-streaming-english", "universal-streaming-multilingual",
            "whisper-rt", "u3-rt-pro", "u3-rt-pro-beta-1", "u3-rt-agent",
            "universal-3-5-pro", "universal-3-6-pro", "universal-3-6",
            "universal-3-7-preview"
        }
        model = self.speech_model
        if model == "universal-streaming":
            model = "universal-streaming-english"

        # Official AssemblyAI v3 Streaming WebSocket endpoint with natural conversational turn silence
        url = (
            f"wss://streaming.assemblyai.com/v3/ws?sample_rate={self.sample_rate}&encoding=pcm_mulaw"
            f"&min_turn_silence=1000&max_turn_silence=2500"
        )
        if model in VALID_MODELS:
            url += f"&speech_model={model}"

        # AssemblyAI v3 requires the raw API key in the Authorization header (no Bearer prefix)
        headers = {"Authorization": self.api_key}

        # Compatible with both websockets 13+ (additional_headers) and older versions (extra_headers)
        sig = inspect.signature(websockets.connect)
        connect_kwargs = {}
        if "additional_headers" in sig.parameters:
            connect_kwargs["additional_headers"] = headers
        else:
            connect_kwargs["extra_headers"] = headers
        if "open_timeout" in sig.parameters:
            connect_kwargs["open_timeout"] = 20.0

        # Fallback IPv4 addresses for systems where upstream DNS has 1s TTL or NAT64 lookup latency
        fallback_ips = ["16.192.28.110", "13.62.236.244", "13.63.152.53"]

        for attempt in range(4):
            try:
                target_url = url
                kwargs = dict(connect_kwargs)
                if attempt > 0 and attempt <= len(fallback_ips):
                    ip = fallback_ips[attempt - 1]
                    target_url = url.replace("streaming.assemblyai.com", ip)
                    ip_headers = dict(headers)
                    ip_headers["Host"] = "streaming.assemblyai.com"
                    if "additional_headers" in sig.parameters:
                        kwargs["additional_headers"] = ip_headers
                    else:
                        kwargs["extra_headers"] = ip_headers
                    kwargs["server_hostname"] = "streaming.assemblyai.com"
                    import ssl
                    kwargs["ssl"] = ssl.create_default_context()
                    logger.info(f"AssemblyAI STT: Trying IPv4 fallback endpoint {ip}...")

                self.ws = await websockets.connect(target_url, **kwargs)
                self.is_connected = True
                self._closed = False

                # Send dynamic configuration to guarantee 1000ms min_turn_silence across all endpoints
                try:
                    await self.ws.send(json.dumps({
                        "type": "UpdateConfiguration",
                        "min_turn_silence": 1000,
                        "max_turn_silence": 2500
                    }))
                except Exception as cfg_err:
                    logger.debug(f"AssemblyAI UpdateConfiguration note: {cfg_err}")

                self._receive_task = asyncio.create_task(self._listen_loop())
                logger.info("Connected to AssemblyAI STT v3 WebSocket stream.")
                break
            except Exception as exc:
                if attempt == 3:
                    logger.error(f"Failed to connect to AssemblyAI STT WebSocket after all attempts: {exc}")
                    await self._dispatch(self.callbacks.on_error, exc)
                    raise exc
                logger.warning(f"Connection attempt {attempt + 1} to AssemblyAI failed ({exc}); retrying in 1s...")
                await asyncio.sleep(1.0)

    async def _dispatch(self, callback, *args):
        """Invoke STT callback safely supporting both sync and async callables."""
        if not callback:
            return
        try:
            res = callback(*args)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            logger.error(f"Error in STT callback execution: {exc}")

    async def send_audio(self, audio_data: bytes):
        """
        Send raw 8kHz μ-law audio frames directly to AssemblyAI streaming endpoint,
        or simulate transcript generation in offline/mock mode.
        """
        if self.ws and self.is_connected and not self._closed and not self.simulated_utterance:
            self._audio_buffer.extend(audio_data)
            # AssemblyAI v3 requires chunk duration between 50ms (400 bytes at 8kHz) and 1000ms
            # We buffer 3 frames (60ms = 480 bytes) before sending
            min_chunk = int(self.sample_rate * 0.06)
            while len(self._audio_buffer) >= min_chunk:
                chunk = bytes(self._audio_buffer[:min_chunk])
                del self._audio_buffer[:min_chunk]
                try:
                    await self.ws.send(chunk)
                except Exception as exc:
                    logger.error(f"Error sending audio to AssemblyAI: {exc}")
                    await self._dispatch(self.callbacks.on_error, exc)
                    break
        elif (not self.api_key or self.simulated_utterance) and self.is_connected and not self._closed:
            # Offline / Mock STT: energy detection and endpointing
            pcm = ulaw_to_pcm(audio_data)
            rms = calculate_rms(pcm)
            if rms >= settings.RMS_ENERGY_THRESHOLD:
                self._speech_frame_count += 1
                self._silence_frame_count = 0
                if self._speech_frame_count == settings.VAD_INTERRUPTION_FRAMES:
                    preview = (self.simulated_utterance or "I want to check availability")[:15]
                    if preview != self._last_interim_transcript:
                        self._last_interim_transcript = preview
                        await self._dispatch(self.callbacks.on_interim, preview)
            else:
                if self._speech_frame_count >= settings.VAD_INTERRUPTION_FRAMES:
                    self._silence_frame_count += 1
                    # Endpoint mock turn using configured silence duration (or 15 frames in test simulation)
                    min_silence_frames = 15 if self.simulated_utterance else max(15, getattr(settings, "SILENCE_ENDPOINTING_MS", 1000) // 20)
                    if self._silence_frame_count >= min_silence_frames:
                        final_text = self.simulated_utterance or "I want to check room availability for next weekend."
                        self._speech_frame_count = 0
                        self._silence_frame_count = 0
                        if final_text != self._last_final_transcript:
                            self._last_final_transcript = final_text
                            logger.info(f"Mock STT: Emitting endpointed final transcript: '{final_text}'")
                            await self._dispatch(self.callbacks.on_final, final_text)

    async def simulate_transcript(self, transcript: str):
        """Explicitly inject a simulated transcript for testing or scripted dialogue."""
        await self._dispatch(self.callbacks.on_interim, transcript[:len(transcript) // 2])
        await self._dispatch(self.callbacks.on_final, transcript)

    async def _listen_loop(self):
        """
        Listen for incoming WebSocket messages from AssemblyAI v3 streaming service.
        Processes Turn messages (interim and final) and lifecycle events.
        """
        try:
            async for message in self.ws:
                if self._closed:
                    break
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "Turn":
                    transcript = data.get("transcript", "").strip()
                    if not transcript:
                        continue

                    end_of_turn = data.get("end_of_turn", False)

                    if end_of_turn:
                        # Final utterance transcript: prevent duplicate emissions
                        if transcript != self._last_final_transcript:
                            self._last_final_transcript = transcript
                            self._last_interim_transcript = None
                            await self._dispatch(self.callbacks.on_final, transcript)
                    else:
                        # Interim / partial transcript
                        if transcript != self._last_interim_transcript:
                            self._last_interim_transcript = transcript
                            await self._dispatch(self.callbacks.on_interim, transcript)

                elif msg_type == "Begin":
                    session_id = data.get("session_id", "unknown")
                    logger.info(f"AssemblyAI STT streaming session initialized: {session_id}")

                elif msg_type == "SpeechStarted":
                    logger.debug("AssemblyAI: Speech onset detected.")

                elif msg_type == "Termination":
                    logger.info("AssemblyAI STT session termination confirmed by server.")

                elif msg_type == "Error":
                    err_msg = data.get("error") or data.get("message") or "Unknown AssemblyAI error"
                    logger.error(f"AssemblyAI STT stream error message: {err_msg}")
                    await self._dispatch(self.callbacks.on_error, RuntimeError(f"AssemblyAI STT Error: {err_msg}"))

        except websockets.exceptions.ConnectionClosed:
            logger.info("AssemblyAI STT WebSocket connection closed normally.")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Error in AssemblyAI STT listen loop: {exc}")
            await self._dispatch(self.callbacks.on_error, exc)

    async def close(self):
        """Gracefully terminate AssemblyAI streaming session and clean up tasks."""
        self._closed = True
        self.is_connected = False

        if self.ws and len(self._audio_buffer) > 0:
            min_50ms = int(self.sample_rate * 0.05)
            if len(self._audio_buffer) < min_50ms:
                self._audio_buffer.extend(b"\xff" * (min_50ms - len(self._audio_buffer)))
            try:
                await self.ws.send(bytes(self._audio_buffer))
            except Exception:
                pass
        self._audio_buffer.clear()

        if self.ws:
            try:
                # Official clean termination protocol for AssemblyAI v3
                await self.ws.send(json.dumps({"type": "Terminate"}))
            except Exception:
                pass

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except (asyncio.CancelledError, Exception):
                pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        logger.info("AssemblyAI STT provider closed.")

    def reset(self):
        """Reset deduplication buffers and interim transcript state."""
        self._last_interim_transcript = None
        self._last_final_transcript = None
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._audio_buffer.clear()
        logger.debug("AssemblyAISTTProvider transcript state reset.")

