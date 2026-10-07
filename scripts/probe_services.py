import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dotenv
dotenv.load_dotenv(override=True)

from app.core.config import settings
from app.llm.gemini import GeminiLLMProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider


async def probe_gemini():
    print("\n--- Probing Gemini LLM ---")
    key = settings.effective_gemini_api_key
    if not key:
        print("[Gemini] No GEMINI_API_KEY or GOOGLE_API_KEY configured.")
        return False
    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "***"
    print(f"[Gemini] Key present: {masked} (length: {len(key)})")

    provider = GeminiLLMProvider()
    if not provider.client:
        print("[Gemini] Provider failed to initialize client.")
        return False

    try:
        messages = [{"role": "user", "content": "Respond with the single word: OK"}]
        chunks = []
        async for chunk in provider.stream_chat(messages):
            if chunk.get("type") == "token":
                chunks.append(chunk.get("content", ""))
        response = "".join(chunks).strip()
        print(f"[Gemini] SUCCESS: Live response received: '{response}'")
        return True
    except Exception as exc:
        print(f"[Gemini] FAILED with error: {exc}")
        return False


async def probe_elevenlabs():
    print("\n--- Probing ElevenLabs TTS ---")
    key = settings.ELEVENLABS_API_KEY
    if not key:
        print("[ElevenLabs] No ELEVENLABS_API_KEY configured.")
        return False
    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "***"
    print(f"[ElevenLabs] Key present: {masked} (length: {len(key)})")
    print(f"[ElevenLabs] Voice ID: {settings.TTS_VOICE_ID}")

    provider = ElevenLabsTTSProvider()
    try:
        audio_chunks = []
        async for chunk in provider.stream_audio("Hello"):
            audio_chunks.append(chunk)
        total_bytes = sum(len(c) for c in audio_chunks)
        if total_bytes > 0:
            print(f"[ElevenLabs] SUCCESS: Synthesized {len(audio_chunks)} chunks ({total_bytes} bytes u-law audio)")
            return True
        else:
            print("[ElevenLabs] No audio chunks returned.")
            return False
    except Exception as exc:
        print(f"[ElevenLabs] FAILED with error: {exc}")
        return False


async def main():
    gemini_ok = await probe_gemini()
    eleven_ok = await probe_elevenlabs()
    print("\n--- Summary ---")
    print(f"Gemini Live:     {'OK' if gemini_ok else 'FAILED/BLOCKED'}")
    print(f"ElevenLabs Live: {'OK' if eleven_ok else 'FAILED/BLOCKED'}")


if __name__ == "__main__":
    asyncio.run(main())
