from abc import ABC, abstractmethod
from typing import AsyncGenerator


class TTSProvider(ABC):
    """Abstract interface for streaming Text-to-Speech synthesis delivering 8kHz μ-law audio."""

    @abstractmethod
    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text into a stream of 8kHz G.711 μ-law audio chunks.
        Must yield bytes ready for 20ms framing.
        """
        pass
