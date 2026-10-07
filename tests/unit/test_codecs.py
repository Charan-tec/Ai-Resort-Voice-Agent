import pytest
from app.telephony.codecs import (
    ULAW_BYTES_PER_FRAME,
    PCM_BYTES_PER_FRAME,
    ulaw_to_pcm,
    pcm_to_ulaw,
    chunk_audio,
    calculate_rms
)


def test_frame_size_constants():
    assert ULAW_BYTES_PER_FRAME == 160
    assert PCM_BYTES_PER_FRAME == 320


def test_ulaw_pcm_roundtrip():
    import struct
    # Generate 160 samples of 16-bit linear PCM audio
    original_pcm = struct.pack("<160h", *[i * 200 for i in range(-80, 80)])
    ulaw = pcm_to_ulaw(original_pcm)
    assert len(ulaw) == 160

    recovered_pcm = ulaw_to_pcm(ulaw)
    assert len(recovered_pcm) == 320

    samples_in = struct.unpack("<160h", original_pcm)
    samples_out = struct.unpack("<160h", recovered_pcm)
    diffs = [abs(a - b) for a, b in zip(samples_in, samples_out)]
    # Maximum quantization error for 16-bit linear PCM in G.711 μ-law
    assert max(diffs) <= 300


def test_chunk_audio():
    sample_audio = b"\x00" * 800  # 5 frames of 160 bytes
    frames = list(chunk_audio(sample_audio, chunk_size=160))
    assert len(frames) == 5
    for f in frames:
        assert len(f) == 160


def test_calculate_rms():
    # Pure silence
    silence = b"\x00" * 320
    assert calculate_rms(silence) == 0.0

    # Louder signal
    ulaw_sound = bytes([128 + (i % 60) for i in range(160)])
    pcm_sound = ulaw_to_pcm(ulaw_sound)
    rms = calculate_rms(pcm_sound)
    assert rms > 0.0
