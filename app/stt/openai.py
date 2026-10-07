import io
import wave
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import logger
from app.stt.base import STTCallback, STTProvider
from app.telephony.codecs import ulaw_to_pcm


class OpenAIWhisperSTTProvider(STTProvider):
    """OpenAI Whisper STT provider buffering audio chunks and transcribing."""

    def __init__(self, callbacks: STTCallback, api_key: Optional[str] = None):
        super().__init__(callbacks)
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self._audio_buffer = bytearray()

    async def connect(self):
        self.is_connected = True
        logger.info("OpenAI Whisper STT provider initialized.")

    async def send_audio(self, audio_data: bytes):
        """Buffer μ-law audio."""
        self._audio_buffer.extend(audio_data)

    async def finalize_chunk(self):
        """Transcribe accumulated buffer."""
        if not self._audio_buffer or not self.client:
            return

        pcm_data = ulaw_to_pcm(bytes(self._audio_buffer))
        self._audio_buffer.clear()

        # Wrap PCM in WAV container
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(pcm_data)
        wav_io.seek(0)
        wav_io.name = "audio.wav"

        try:
            resp = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_io,
                language="en"
            )
            text = resp.text.strip()
            if text and self.callbacks.on_final:
                await self.callbacks.on_final(text)
        except Exception as exc:
            logger.error(f"OpenAI Whisper transcription error: {exc}")
            if self.callbacks.on_error:
                await self.callbacks.on_error(exc)

    async def close(self):
        self.is_connected = False
        self._audio_buffer.clear()
