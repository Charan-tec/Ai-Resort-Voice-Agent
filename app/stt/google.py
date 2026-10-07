import asyncio
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.stt.base import STTCallback, STTProvider


class GoogleSpeechSTTProvider(STTProvider):
    """Google Cloud Speech-to-Text streaming provider abstraction."""

    def __init__(self, callbacks: STTCallback, credentials_path: Optional[str] = None):
        super().__init__(callbacks)
        self.credentials_path = credentials_path or settings.GOOGLE_APPLICATION_CREDENTIALS
        self._audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def connect(self):
        self.is_connected = True
        logger.info("Google Cloud Speech STT provider initialized.")

    async def send_audio(self, audio_data: bytes):
        if self.is_connected:
            await self._audio_queue.put(audio_data)

    async def close(self):
        self.is_connected = False
        await self._audio_queue.put(None)
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
