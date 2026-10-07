import time
from typing import Callable, Optional
from app.core.config import settings
from app.core.logging import logger
from app.telephony.codecs import calculate_rms, ulaw_to_pcm


class EnergyGate:
    """
    RMS Energy Gate for real-time speech onset and interruption detection on 20ms frames.
    Maintains a running noise baseline and detects sustained energy spikes exceeding threshold.
    """

    def __init__(
        self,
        base_threshold: float = 450.0,
        consecutive_frames: int = 3,
        alpha: float = 0.95,
        on_interruption: Optional[Callable[[], None]] = None
    ):
        self.base_threshold = base_threshold
        self.consecutive_frames = consecutive_frames
        self.alpha = alpha
        self.on_interruption = on_interruption

        self.noise_floor = 150.0
        self._above_threshold_count = 0
        self._is_active = False
        self._last_speech_time = 0.0

    def reset(self):
        """Reset gate counters."""
        self._above_threshold_count = 0
        self._is_active = False

    def process_frame(self, ulaw_frame: bytes, is_assistant_speaking: bool = False) -> dict:
        """
        Process a single 20ms μ-law frame (160 bytes).
        Returns dict with current RMS, speech detection status, and whether barge-in triggered.
        """
        pcm_frame = ulaw_to_pcm(ulaw_frame)
        rms = calculate_rms(pcm_frame)

        # Update running noise floor when not speaking
        if rms < self.base_threshold:
            self.noise_floor = self.alpha * self.noise_floor + (1.0 - self.alpha) * rms
            self._above_threshold_count = 0
            is_speech = False
        else:
            self._above_threshold_count += 1
            is_speech = True

        barge_in_triggered = False

        # If sustained speech above threshold detected
        if self._above_threshold_count >= self.consecutive_frames:
            self._last_speech_time = time.monotonic()
            self._is_active = True

            # If assistant is currently speaking, this triggers a barge-in interruption!
            if is_assistant_speaking:
                barge_in_triggered = True
                logger.info(
                    f"EnergyGate: Barge-in triggered! RMS={rms:.1f} (Threshold={self.base_threshold:.1f}, "
                    f"Frames={self._above_threshold_count})"
                )
                if self.on_interruption:
                    self.on_interruption()

        return {
            "rms": rms,
            "noise_floor": self.noise_floor,
            "is_speech": is_speech,
            "barge_in": barge_in_triggered,
            "consecutive_count": self._above_threshold_count
        }
