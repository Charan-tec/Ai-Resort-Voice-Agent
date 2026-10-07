import asyncio
import json
from typing import Optional
import websockets
from app.core.config import settings
from app.core.logging import logger
from app.stt.base import STTCallback, STTProvider
from app.telephony.codecs import calculate_rms, ulaw_to_pcm


class DeepgramSTTProvider(STTProvider):
    """
    Streaming STT implementation using Deepgram Nova-2 via WebSockets.
    Sends raw 8kHz μ-law directly, receiving low-latency interim and final transcripts.
    When operating in offline/mock mode, detects audio energy and silence endpointing
    to simulate transcription turns for local testing and call simulation.
    """

    def __init__(
        self,
        callbacks: STTCallback,
        api_key: Optional[str] = None,
        simulated_utterance: Optional[str] = None
    ):
        super().__init__(callbacks)
        self.api_key = api_key or settings.DEEPGRAM_API_KEY
        self.simulated_utterance = simulated_utterance
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._closed = False
        # Offline simulation state
        self._speech_frame_count = 0
        self._silence_frame_count = 0

    async def connect(self):
        if not self.api_key:
            logger.warning("Deepgram API key not provided; operating in offline/mock STT mode.")
            self.is_connected = True
            return

        url = (
            "wss://api.deepgram.com/v1/listen?"
            "encoding=mulaw&sample_rate=8000&channels=1"
            "&model=nova-2-phonecall&interim_results=true&endpointing=300"
        )
        headers = {"Authorization": f"Token {self.api_key}"}

        try:
            self.ws = await websockets.connect(url, extra_headers=headers)
            self.is_connected = True
            self._closed = False
            self._receive_task = asyncio.create_task(self._listen_loop())
            logger.info("Connected to Deepgram STT WebSocket stream.")
        except Exception as exc:
            logger.error(f"Failed to connect to Deepgram STT: {exc}")
            if self.callbacks.on_error:
                await self.callbacks.on_error(exc)
            raise exc

    async def send_audio(self, audio_data: bytes):
        """Send 8kHz μ-law audio frames."""
        if self.ws and self.is_connected and not self._closed:
            try:
                await self.ws.send(audio_data)
            except Exception as exc:
                logger.error(f"Error sending audio to Deepgram: {exc}")
        elif not self.api_key and self.is_connected and not self._closed:
            # Offline / Mock STT: speech detection on audio frames with energy
            pcm = ulaw_to_pcm(audio_data)
            rms = calculate_rms(pcm)
            if rms >= settings.RMS_ENERGY_THRESHOLD:
                self._speech_frame_count += 1
                self._silence_frame_count = 0
                if self._speech_frame_count == settings.VAD_INTERRUPTION_FRAMES:
                    preview = (self.simulated_utterance or "I want to check availability")[:15]
                    if self.callbacks.on_interim:
                        await self.callbacks.on_interim(preview)
            else:
                if self._speech_frame_count >= settings.VAD_INTERRUPTION_FRAMES:
                    self._silence_frame_count += 1
                    # 15 frames of silence (~300ms) after speech indicates endpointing
                    if self._silence_frame_count >= 15:
                        final_text = self.simulated_utterance or "I want to check room availability for next weekend."
                        self._speech_frame_count = 0
                        self._silence_frame_count = 0
                        logger.info(f"Mock STT: Emitting endpointed final transcript: '{final_text}'")
                        if self.callbacks.on_final:
                            await self.callbacks.on_final(final_text)

    async def simulate_transcript(self, transcript: str):
        """Explicitly inject a simulated transcript for testing or scripted dialogue."""
        if self.callbacks.on_interim:
            await self.callbacks.on_interim(transcript[:len(transcript) // 2])
        if self.callbacks.on_final:
            await self.callbacks.on_final(transcript)

    async def _listen_loop(self):
        try:
            async for message in self.ws:
                if self._closed:
                    break
                data = json.loads(message)
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if not alternatives:
                    continue

                transcript = alternatives[0].get("transcript", "").strip()
                if not transcript:
                    continue

                is_final = data.get("is_final", False)
                speech_final = data.get("speech_final", False)

                if (is_final or speech_final) and self.callbacks.on_final:
                    await self.callbacks.on_final(transcript)
                elif self.callbacks.on_interim:
                    await self.callbacks.on_interim(transcript)

        except websockets.exceptions.ConnectionClosed:
            logger.info("Deepgram STT connection closed normally.")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Error in Deepgram STT listen loop: {exc}")
            if self.callbacks.on_error:
                await self.callbacks.on_error(exc)

    async def close(self):
        self._closed = True
        self.is_connected = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        logger.info("Deepgram STT provider closed.")

    def reset(self):
        """Reset deduplication buffers and interim transcript state."""
        self._last_interim_transcript = None
        self._last_final_transcript = None
        logger.debug("DeepgramSTTProvider transcript state reset.")

