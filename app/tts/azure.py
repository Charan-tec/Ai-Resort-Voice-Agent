from typing import AsyncGenerator, Optional
from app.core.config import settings
from app.core.logging import logger
from app.tts.base import TTSProvider


class AzureSpeechTTSProvider(TTSProvider):
    """Azure Speech TTS provider abstraction with raw-8khz-8bit-mono-mulaw output."""

    def __init__(
        self,
        subscription_key: Optional[str] = None,
        region: Optional[str] = None,
        voice_name: str = "en-US-JennyNeural"
    ):
        self.key = subscription_key or settings.AZURE_SPEECH_KEY
        self.region = region or settings.AZURE_SPEECH_REGION
        self.voice_name = voice_name

    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        if not text.strip():
            return
        # In mock / fallback mode:
        yield b"\xff" * 1600
