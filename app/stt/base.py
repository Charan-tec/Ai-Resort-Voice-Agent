from abc import ABC, abstractmethod
from typing import Callable, Coroutine, Optional


class STTCallback:
    """Callbacks dispatched by STT providers on interim and final transcription results."""
    def __init__(
        self,
        on_interim: Optional[Callable[[str], Coroutine]] = None,
        on_final: Optional[Callable[[str], Coroutine]] = None,
        on_error: Optional[Callable[[Exception], Coroutine]] = None
    ):
        self.on_interim = on_interim
        self.on_final = on_final
        self.on_error = on_error


class STTProvider(ABC):
    """Abstract interface for streaming Speech-to-Text providers."""

    def __init__(self, callbacks: STTCallback):
        self.callbacks = callbacks
        self.is_connected = False

    @abstractmethod
    async def connect(self):
        """Establish connection to STT streaming service."""
        pass

    @abstractmethod
    async def send_audio(self, audio_data: bytes):
        """Stream audio chunk (8kHz μ-law or linear PCM)."""
        pass

    @abstractmethod
    async def close(self):
        """Gracefully close STT connection."""
        pass

    def reset(self):
        """Reset internal transcript buffers or state."""
        pass

