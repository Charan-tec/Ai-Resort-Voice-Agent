from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import logger
from app.telephony.codecs import pcm_to_ulaw
from app.tts.base import TTSProvider


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS streaming provider, converting output PCM to 8kHz μ-law."""

    def __init__(self, api_key: Optional[str] = None, model: str = "tts-1", voice: str = "alloy"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.voice = voice
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        if not text.strip():
            return
        if not self.client:
            yield b"\xff" * 1600
            return

        try:
            response = await self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="pcm"  # 24kHz linear PCM
            )
            raw_pcm = response.content
            # Downsample 24kHz -> 8kHz (take every 3rd 16-bit sample)
            downsampled_pcm = bytearray()
            for i in range(0, len(raw_pcm), 6):
                downsampled_pcm.extend(raw_pcm[i:i+2])
            ulaw_audio = pcm_to_ulaw(bytes(downsampled_pcm))
            yield ulaw_audio
        except Exception as exc:
            logger.error(f"OpenAI TTS error: {exc}")
