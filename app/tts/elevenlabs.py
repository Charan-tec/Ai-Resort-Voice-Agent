import asyncio
from typing import AsyncGenerator, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.tts.base import TTSProvider


class ElevenLabsTTSProvider(TTSProvider):
    """
    ElevenLabs Flash streaming TTS delivering native 8kHz G.711 μ-law audio.
    Targets sub-300ms time to first audio chunk.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_flash_v2_5"
    ):
        self.api_key = api_key if api_key is not None else settings.ELEVENLABS_API_KEY
        self.voice_id = voice_id or settings.TTS_VOICE_ID
        self.model_id = model_id
        self.output_format = "ulaw_8000"

    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        if not text.strip():
            return

        if not self.api_key:
            # Generate simulated audio frames for offline testing
            logger.debug("ElevenLabs API key not set; generating mock 8kHz μ-law frames.")
            yield b"\xff" * 3200  # ~200ms of silence/tone
            return

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream?output_format={self.output_format}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "optimize_streaming_latency": 4
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"ElevenLabs TTS HTTP {response.status_code}: {error_text.decode('utf-8', errors='ignore')}")
                        yield b"\xff" * 3200
                        return

                    async for chunk in response.aiter_bytes(chunk_size=160):
                        if chunk:
                            yield chunk
        except Exception as exc:
            logger.error(f"ElevenLabs TTS exception: {exc}")
            yield b"\xff" * 3200
