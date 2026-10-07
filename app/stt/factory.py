from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.stt.base import STTCallback, STTProvider
from app.stt.assemblyai import AssemblyAISTTProvider
from app.stt.deepgram import DeepgramSTTProvider
from app.stt.openai import OpenAIWhisperSTTProvider
from app.stt.google import GoogleSpeechSTTProvider


def get_stt_provider(
    callbacks: STTCallback,
    provider_name: Optional[str] = None,
    simulated_utterance: Optional[str] = None
) -> STTProvider:
    """
    Factory function returning the configured streaming STT provider.
    Defaults to AssemblyAI as primary provider.
    """
    provider = (provider_name or settings.STT_PROVIDER or "assemblyai").strip().lower()

    if provider in ("assemblyai", "assembly", "aai"):
        logger.debug("Instantiating AssemblyAISTTProvider")
        return AssemblyAISTTProvider(
            callbacks=callbacks,
            simulated_utterance=simulated_utterance
        )
    elif provider == "deepgram":
        logger.debug("Instantiating DeepgramSTTProvider")
        return DeepgramSTTProvider(
            callbacks=callbacks,
            simulated_utterance=simulated_utterance
        )
    elif provider == "openai":
        logger.debug("Instantiating OpenAIWhisperSTTProvider")
        return OpenAIWhisperSTTProvider(callbacks=callbacks)
    elif provider in ("google", "gemini"):
        logger.debug("Instantiating GoogleSpeechSTTProvider")
        return GoogleSpeechSTTProvider(callbacks=callbacks)
    else:
        logger.warning(f"Unknown STT provider '{provider}', defaulting to AssemblyAI")
        return AssemblyAISTTProvider(
            callbacks=callbacks,
            simulated_utterance=simulated_utterance
        )
