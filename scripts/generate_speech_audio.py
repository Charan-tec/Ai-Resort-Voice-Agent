import subprocess
import wave
import audioop
import os
import sys

# Windows PowerShell script to synthesize speech to a WAV file
ps_script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('temp_speech.wav')
$synth.Speak('Hello, I want to check room availability for an ocean villa.')
$synth.Dispose()
"""

with open("temp_synth.ps1", "w", encoding="utf-8") as f:
    f.write(ps_script)

try:
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "temp_synth.ps1"], check=True)
    with wave.open("temp_speech.wav", "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        n_frames = w.getnframes()
        raw_pcm = w.readframes(n_frames)
        print(f"Original WAV: {n_channels} channels, {sampwidth} bytes/sample, {framerate} Hz, {n_frames} frames")

    # If stereo, convert to mono
    if n_channels == 2:
        raw_pcm = audioop.tomono(raw_pcm, sampwidth, 1, 1)

    # Convert sample rate to 8000 Hz if needed
    if framerate != 8000:
        raw_pcm, _ = audioop.ratecv(raw_pcm, sampwidth, 1, framerate, 8000, None)

    # Convert 16-bit PCM to μ-law (8kHz)
    ulaw_audio = audioop.lin2ulaw(raw_pcm, 2)
    with open("test_speech_8k.ulaw", "wb") as f:
        f.write(ulaw_audio)

    print(f"Converted 8kHz μ-law audio saved: {len(ulaw_audio)} bytes ({len(ulaw_audio)/8000:.2f} seconds)")

finally:
    if os.path.exists("temp_synth.ps1"):
        os.remove("temp_synth.ps1")
    if os.path.exists("temp_speech.wav"):
        os.remove("temp_speech.wav")
