#!/usr/bin/env python3
"""
Jarvis Voice Assistant
Wake word -> Record -> Transcribe -> Send to Hermes
"""

import os
import wave
import tempfile
import subprocess
import numpy as np
import pyaudio
from openwakeword.model import Model
from faster_whisper import WhisperModel

# --- Config ---
WAKEWORD_MODEL = os.path.expanduser(
    "~/.local/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"
)
WAKEWORD_THRESHOLD = 0.5
DEVICE_RATE = 48000        # Hardware sample rate
TARGET_RATE = 16000        # Rate required by openWakeWord and Whisper
DEVICE_INDEX = 1           # USB-C Speaker/Mic
CHUNK_SIZE = 3840          # 80ms at 48kHz (downsamples to 1280 at 16kHz)
RECORD_SECONDS = 8         # Max recording time after wake word
SILENCE_THRESHOLD = 500    # Amplitude threshold to detect silence
SILENCE_SECONDS = 2        # Stop recording after this many seconds of silence
WHISPER_MODEL = "tiny"     # tiny/base/small — tiny is fastest on Pi


def downsample(data, from_rate, to_rate):
    """Simple downsample by integer factor."""
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    factor = from_rate // to_rate
    resampled = audio[::factor]
    return resampled.astype(np.int16).tobytes()


# --- Init ---
print("Loading wake word model...")
oww = Model(wakeword_model_paths=[WAKEWORD_MODEL])

print(f"Loading Whisper ({WHISPER_MODEL})...")
whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

audio = pyaudio.PyAudio()

print("\n✓ Ready. Say 'Hey Jarvis' to begin.\n")


def record_after_wakeword():
    """Record audio until silence or max duration."""
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=DEVICE_RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK_SIZE,
    )

    print("🎙 Listening...")
    frames = []
    silent_chunks = 0
    max_chunks = int(DEVICE_RATE / CHUNK_SIZE * RECORD_SECONDS)
    silence_chunks_limit = int(DEVICE_RATE / CHUNK_SIZE * SILENCE_SECONDS)

    for _ in range(max_chunks):
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        frames.append(downsample(data, DEVICE_RATE, TARGET_RATE))
        amplitude = np.frombuffer(data, dtype=np.int16)
        if np.abs(amplitude).mean() < SILENCE_THRESHOLD:
            silent_chunks += 1
        else:
            silent_chunks = 0
        if silent_chunks >= silence_chunks_limit:
            break

    stream.stop_stream()
    stream.close()
    return frames


def transcribe(frames):
    """Save frames to temp WAV and transcribe with Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(TARGET_RATE)
        wf.writeframes(b"".join(frames))

    segments, _ = whisper.transcribe(tmp_path, language="en")
    text = " ".join(s.text.strip() for s in segments).strip()
    os.unlink(tmp_path)
    return text


def send_to_hermes(text):
    """Send transcribed text to Hermes CLI and print response."""
    print(f"\nYou: {text}")
    print("Hermes: ", end="", flush=True)
    result = subprocess.run(
        ["hermes", "--prompt", text, "--no-stream"],
        capture_output=True,
        text=True,
    )
    response = result.stdout.strip() or result.stderr.strip()
    print(response)
    print()


def listen_for_wakeword():
    """Continuously listen for wake word."""
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=DEVICE_RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK_SIZE,
    )

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            pcm = np.frombuffer(downsample(data, DEVICE_RATE, TARGET_RATE), dtype=np.int16)
            prediction = oww.predict(pcm)

            for model_name, score in prediction.items():
                if score > WAKEWORD_THRESHOLD:
                    print(f"\n⚡ Wake word detected! (score: {score:.2f})")
                    stream.stop_stream()
                    stream.close()

                    frames = record_after_wakeword()
                    text = transcribe(frames)

                    if text:
                        send_to_hermes(text)
                    else:
                        print("(Nothing heard, try again)\n")

                    # Reopen stream
                    stream = audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=DEVICE_RATE,
                        input=True,
                        input_device_index=DEVICE_INDEX,
                        frames_per_buffer=CHUNK_SIZE,
                    )
                    oww.reset_states()
                    print("✓ Listening for 'Hey Jarvis'...\n")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    listen_for_wakeword()
