import math
import struct
from typing import Generator, List

# Frame constants for 8kHz, 20ms audio
SAMPLE_RATE = 8000
FRAME_MS = 20
ULAW_BYTES_PER_FRAME = 160  # 8000 samples/sec * 0.02s = 160 bytes
PCM_BYTES_PER_FRAME = 320   # 160 samples * 2 bytes/sample = 320 bytes

# Pre-generate μ-law decode lookup table (256 entries -> 16-bit signed int)
_ULAW_DECODE_TABLE = []
for i in range(256):
    byte = ~i & 0xFF
    sign = -1 if (byte & 0x80) else 1
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    sample = sign * ((mantissa << 3) + 0x84) << exponent
    sample -= sign * 0x84
    # Clamp to signed 16-bit
    sample = max(-32768, min(32767, sample))
    _ULAW_DECODE_TABLE.append(sample)


def ulaw_to_pcm(ulaw_data: bytes) -> bytes:
    """Convert G.711 μ-law bytes to 16-bit signed linear PCM (little-endian)."""
    samples = [_ULAW_DECODE_TABLE[b] for b in ulaw_data]
    return struct.pack(f"<{len(samples)}h", *samples)


# Pre-generate PCM to μ-law encoding lookup table for 16-bit linear PCM
_PCM_TO_ULAW_MAP = bytearray(65536)
BIAS = 0x84
CLIP = 32635

for val in range(-32768, 32768):
    sign = 0x80 if val < 0 else 0x00
    mag = -val if val < 0 else val
    if mag > CLIP:
        mag = CLIP
    mag += BIAS

    exponent = 7
    for exp in range(7, -1, -1):
        if mag >= (1 << (exp + 7)):
            exponent = exp
            break

    mantissa = (mag >> (exponent + 3)) & 0x0F
    encoded = ~(sign | (exponent << 4) | mantissa) & 0xFF
    _PCM_TO_ULAW_MAP[val + 32768] = encoded


def pcm_to_ulaw(pcm_data: bytes) -> bytes:
    """Convert 16-bit signed linear PCM bytes (little-endian) to G.711 μ-law bytes."""
    if not pcm_data:
        return b""
    # Discard trailing incomplete byte if odd length
    if len(pcm_data) % 2 != 0:
        pcm_data = pcm_data[:len(pcm_data) - 1]
    num_samples = len(pcm_data) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm_data)
    encoded = bytes(_PCM_TO_ULAW_MAP[s + 32768] for s in samples)
    return encoded


def chunk_audio(data: bytes, chunk_size: int = ULAW_BYTES_PER_FRAME) -> Generator[bytes, None, None]:
    """Yield fixed-size audio frames."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def calculate_rms(pcm_data: bytes) -> float:
    """Calculate Root Mean Square (RMS) energy of 16-bit linear PCM audio."""
    if not pcm_data or len(pcm_data) < 2:
        return 0.0
    if len(pcm_data) % 2 != 0:
        pcm_data = pcm_data[:len(pcm_data) - 1]
    num_samples = len(pcm_data) // 2
    if num_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{num_samples}h", pcm_data)
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / num_samples)

