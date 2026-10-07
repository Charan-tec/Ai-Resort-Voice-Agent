import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.config import settings
from app.stt.base import STTCallback
from app.stt.assemblyai import AssemblyAISTTProvider
from app.stt.factory import get_stt_provider
from app.stt.deepgram import DeepgramSTTProvider
from app.stt.openai import OpenAIWhisperSTTProvider
from app.stt.google import GoogleSpeechSTTProvider
from app.telephony.codecs import ULAW_BYTES_PER_FRAME
from scripts.simulate_call import generate_tone_frame


@pytest.mark.asyncio
async def test_assemblyai_offline_mock_mode_when_no_api_key():
    """Verify that when no API key is provided, AssemblyAI operates in offline/mock mode."""
    interim_results = []
    final_results = []

    callbacks = STTCallback(
        on_interim=lambda text: interim_results.append(text),
        on_final=lambda text: final_results.append(text),
        on_error=lambda err: None
    )

    provider = AssemblyAISTTProvider(
        callbacks=callbacks,
        api_key="",
        simulated_utterance="I want to book an ocean villa."
    )

    await provider.connect()
    assert provider.is_connected is True
    assert provider.ws is None

    # Simulate speaking with audible tone frames
    speech_frame = generate_tone_frame(freq=400.0, amplitude=4500.0)
    for _ in range(settings.VAD_INTERRUPTION_FRAMES + 2):
        await provider.send_audio(speech_frame)

    assert len(interim_results) >= 1
    assert "I want to book" in interim_results[0]

    # Followed by 15 frames of silence for endpointing
    silence_frame = b"\xff" * ULAW_BYTES_PER_FRAME
    for _ in range(16):
        await provider.send_audio(silence_frame)

    assert len(final_results) == 1
    assert final_results[0] == "I want to book an ocean villa."

    await provider.close()
    assert provider.is_connected is False


@pytest.mark.asyncio
async def test_assemblyai_simulate_transcript():
    """Verify explicit simulated transcript injection."""
    interims = []
    finals = []

    callbacks = STTCallback(
        on_interim=lambda t: interims.append(t),
        on_final=lambda t: finals.append(t)
    )

    provider = AssemblyAISTTProvider(callbacks=callbacks, api_key=None)
    await provider.simulate_transcript("Check availability for next weekend")

    assert len(interims) == 1
    assert len(finals) == 1
    assert finals[0] == "Check availability for next weekend"
    await provider.close()


@pytest.mark.asyncio
async def test_assemblyai_connect_and_stream_with_mocked_ws():
    """Verify WebSocket connection parameters, Authorization header, and audio streaming."""
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    callbacks = STTCallback()
    provider = AssemblyAISTTProvider(
        callbacks=callbacks,
        api_key="test_assembly_key_12345",
        sample_rate=8000
    )

    with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_ws
        await provider.connect()

        assert provider.is_connected is True
        mock_connect.assert_called_once()
        call_args, call_kwargs = mock_connect.call_args
        assert "streaming.assemblyai.com/v3/ws" in call_args[0]
        assert "sample_rate=8000" in call_args[0]
        assert "encoding=pcm_mulaw" in call_args[0]

        # Verify Authorization header contains raw API key without Bearer
        headers = call_kwargs.get("additional_headers") or call_kwargs.get("extra_headers")
        assert headers == {"Authorization": "test_assembly_key_12345"}

        # Send 3 x 160-byte audio frames (480 bytes = 60ms chunk meeting AssemblyAI's >=50ms constraint)
        test_audio = b"\x80" * 480
        await provider.send_audio(test_audio)
        mock_ws.send.assert_called_with(test_audio)

        # Close session
        await provider.close()
        # Verify Terminate message was sent
        terminate_call_found = any(
            '{"type": "Terminate"}' in str(c) for c in mock_ws.send.call_args_list
        )
        assert terminate_call_found, "Expected Terminate JSON event on close"
        mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_assemblyai_listen_loop_turn_events_and_deduplication():
    """Verify that Turn messages trigger on_interim and on_final without duplicates."""
    interims = []
    finals = []
    errors = []

    callbacks = STTCallback(
        on_interim=lambda t: interims.append(t),
        on_final=lambda t: finals.append(t),
        on_error=lambda e: errors.append(e)
    )

    provider = AssemblyAISTTProvider(callbacks=callbacks, api_key="test_key")

    # Sequence of incoming messages
    messages = [
        json.dumps({"type": "Begin", "session_id": "sess_123"}),
        json.dumps({"type": "SpeechStarted"}),
        json.dumps({"type": "Turn", "transcript": "Hello", "end_of_turn": False}),
        json.dumps({"type": "Turn", "transcript": "Hello", "end_of_turn": False}),  # Duplicate partial
        json.dumps({"type": "Turn", "transcript": "Hello, I want to book", "end_of_turn": False}),
        json.dumps({"type": "Turn", "transcript": "Hello, I want to book a villa.", "end_of_turn": True}),
        json.dumps({"type": "Turn", "transcript": "Hello, I want to book a villa.", "end_of_turn": True}),  # Duplicate final
        json.dumps({"type": "Turn", "transcript": "", "end_of_turn": False}),  # Empty
        json.dumps({"type": "Termination"}),
    ]

    class AsyncMessageIterator:
        def __init__(self, items):
            self.items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            await asyncio.sleep(0.001)
            return self.items.pop(0)

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = lambda s: AsyncMessageIterator(messages)
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_ws
        await provider.connect()
        # Await listen loop task until iterator completes
        if provider._receive_task:
            await provider._receive_task

        assert interims == ["Hello", "Hello, I want to book"]
        assert finals == ["Hello, I want to book a villa."]
        assert len(errors) == 0

        await provider.close()


@pytest.mark.asyncio
async def test_assemblyai_listen_loop_error_event():
    """Verify that an Error message triggers on_error callback."""
    errors = []
    callbacks = STTCallback(
        on_error=lambda e: errors.append(e)
    )
    provider = AssemblyAISTTProvider(callbacks=callbacks, api_key="test_key")

    messages = [
        json.dumps({"type": "Error", "error": "Invalid audio encoding"})
    ]

    class AsyncMessageIterator:
        def __init__(self, items):
            self.items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = lambda s: AsyncMessageIterator(messages)
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_ws
        await provider.connect()
        if provider._receive_task:
            await provider._receive_task

        assert len(errors) == 1
        assert "Invalid audio encoding" in str(errors[0])
        await provider.close()


def test_stt_factory_resolution():
    """Verify get_stt_provider dynamically resolves configured STT providers."""
    cb = STTCallback()

    # AssemblyAI
    p_assembly = get_stt_provider(callbacks=cb, provider_name="assemblyai")
    assert isinstance(p_assembly, AssemblyAISTTProvider)

    # Deepgram fallback
    p_deepgram = get_stt_provider(callbacks=cb, provider_name="deepgram")
    assert isinstance(p_deepgram, DeepgramSTTProvider)

    # OpenAI
    p_openai = get_stt_provider(callbacks=cb, provider_name="openai")
    assert isinstance(p_openai, OpenAIWhisperSTTProvider)

    # Google
    p_google = get_stt_provider(callbacks=cb, provider_name="google")
    assert isinstance(p_google, GoogleSpeechSTTProvider)

    # Unknown defaults to AssemblyAI
    p_unknown = get_stt_provider(callbacks=cb, provider_name="nonexistent_provider")
    assert isinstance(p_unknown, AssemblyAISTTProvider)


@pytest.mark.asyncio
async def test_assemblyai_turn_manager_integration():
    """Verify AssemblyAI final transcripts transition TurnManager state correctly."""
    from app.orchestrator.turn_manager import TurnManager, TurnState

    turns_received = []

    async def on_user_turn_ready(user_text: str):
        turns_received.append(user_text)

    turn_manager = TurnManager(
        on_barge_in=AsyncMock(),
        on_user_turn_ready=on_user_turn_ready
    )

    cb = STTCallback(
        on_final=turn_manager.handle_user_speech_final
    )
    provider = AssemblyAISTTProvider(callbacks=cb, api_key=None)
    await provider.simulate_transcript("Do you have ocean villas?")
    await asyncio.sleep(0.02)

    assert len(turns_received) == 1
    assert turns_received[0] == "Do you have ocean villas?"
    await provider.close()


@pytest.mark.asyncio
async def test_assemblyai_cancel_and_resource_cleanup():
    """Verify proper task cancellation and clean shutdown on close."""
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()

    provider = AssemblyAISTTProvider(callbacks=STTCallback(), api_key="dummy_key")

    with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_ws
        await provider.connect()
        assert provider._receive_task is not None
        assert not provider._receive_task.done()

        # Trigger close
        await provider.close()
        assert provider.is_connected is False
        assert provider._closed is True
        assert provider._receive_task.done() or provider._receive_task.cancelled()

