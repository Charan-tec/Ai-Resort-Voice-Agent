import pytest
from app.audio.energy_gate import EnergyGate
from app.telephony.codecs import pcm_to_ulaw
import struct


def test_energy_gate_silence():
    gate = EnergyGate(base_threshold=450.0, consecutive_frames=3)
    # Generate silence frames (PCM 0s)
    silence_pcm = struct.pack("<160h", *([0] * 160))
    silence_ulaw = pcm_to_ulaw(silence_pcm)

    for _ in range(5):
        result = gate.process_frame(silence_ulaw, is_assistant_speaking=False)
        assert result["is_speech"] is False
        assert result["barge_in"] is False


def test_energy_gate_speech_and_barge_in():
    interruption_fired = False

    def on_interrupt():
        nonlocal interruption_fired
        interruption_fired = True

    gate = EnergyGate(
        base_threshold=400.0,
        consecutive_frames=3,
        on_interruption=on_interrupt
    )

    # Generate high amplitude speech frame (sine/amplitude 5000)
    loud_pcm = struct.pack("<160h", *([5000 if i % 2 == 0 else -5000 for i in range(160)]))
    loud_ulaw = pcm_to_ulaw(loud_pcm)

    # First frame: speech detected, but not yet reached 3 consecutive frames
    res1 = gate.process_frame(loud_ulaw, is_assistant_speaking=True)
    assert res1["is_speech"] is True
    assert res1["barge_in"] is False
    assert not interruption_fired

    # Second frame
    res2 = gate.process_frame(loud_ulaw, is_assistant_speaking=True)
    assert res2["is_speech"] is True
    assert res2["barge_in"] is False

    # Third frame: hits consecutive_frames threshold while assistant speaking -> barge-in!
    res3 = gate.process_frame(loud_ulaw, is_assistant_speaking=True)
    assert res3["is_speech"] is True
    assert res3["barge_in"] is True
    assert interruption_fired is True
