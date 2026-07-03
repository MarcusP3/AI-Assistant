#!/usr/bin/env python3
"""
Jarvis Voice Assistant
Wake word -> Record -> Transcribe -> Send to Hermes -> Speak response
"""

import os
import re
import sys
import string
import wave
import tempfile
import subprocess
import numpy as np
import pyaudio
from openwakeword.model import Model
from faster_whisper import WhisperModel

# --- Config ---
_PY_VER = f"{sys.version_info.major}.{sys.version_info.minor}"
WAKEWORD_MODEL = os.path.expanduser(
    f"~/.local/lib/python{_PY_VER}/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"
)
WAKEWORD_THRESHOLD = 0.5
DEVICE_RATE = 48000        # Hardware sample rate
TARGET_RATE = 16000        # Rate required by openWakeWord and Whisper
DEVICE_INDEX = 1           # USB-C Speaker/Mic
CHUNK_SIZE = 3840          # 80ms at 48kHz (downsamples to 1280 at 16kHz)
RECORD_SECONDS = 8         # Max recording time after speech starts
SPEECH_WAIT_SECONDS = 10   # Max seconds to wait for speech to begin
SILENCE_THRESHOLD = 500    # Amplitude threshold to detect silence
SILENCE_SECONDS = 2        # Stop recording after this many seconds of trailing silence
WHISPER_MODEL = "base"     # tiny/base/small — base recognizes "Jarvis" far better than tiny
HERMES_TIMEOUT = 60        # Seconds to wait for Hermes response before giving up

# Piper TTS config
PIPER_BINARY = os.path.expanduser("~/.local/bin/piper")
PIPER_VOICE = os.path.expanduser("~/.local/share/piper/en_US-lessac-medium.onnx")

# Strip ANSI escape codes (color/formatting) from Hermes output
_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi(text):
    return _ANSI_ESCAPE.sub('', text)


def downsample(data, from_rate, to_rate):
    """Simple downsample by integer factor."""
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    factor = from_rate // to_rate
    resampled = audio[::factor]
    return resampled.astype(np.int16).tobytes()


def speak(text):
    """Convert text to speech using Piper and play it."""
    if not os.path.exists(PIPER_BINARY):
        print(f"[TTS] Piper not found at {PIPER_BINARY} — skipping speech.")
        return
    if not os.path.exists(PIPER_VOICE):
        print(f"[TTS] Voice model not found at {PIPER_VOICE} — skipping speech.")
        return

    try:
        piper_proc = subprocess.Popen(
            [PIPER_BINARY, "--model", PIPER_VOICE, "--output-raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        aplay_proc = subprocess.Popen(
            ["aplay", "-q", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
            stdin=piper_proc.stdout,
            stderr=subprocess.PIPE,
        )
        # Close our copy of piper's stdout so aplay is the only reader;
        # this lets piper get SIGPIPE if aplay dies, instead of hanging.
        piper_proc.stdout.close()
        try:
            piper_proc.stdin.write(text.encode())
            piper_proc.stdin.close()
        except BrokenPipeError:
            pass  # piper exited early; error is reported below

        aplay_proc.wait()
        piper_proc.wait()

        if piper_proc.returncode not in (0, None):
            err = piper_proc.stderr.read().decode(errors="ignore").strip()
            print(f"[TTS] Piper failed (exit {piper_proc.returncode}): {err or 'no output'}")
        elif aplay_proc.returncode not in (0, None):
            err = aplay_proc.stderr.read().decode(errors="ignore").strip()
            print(f"[TTS] aplay failed (exit {aplay_proc.returncode}): {err or 'no output'}")
    except Exception as e:
        print(f"[TTS] Error: {e}")


# --- Init ---
print("Loading wake word model...")
if not os.path.exists(WAKEWORD_MODEL):
    print(f"ERROR: Wake word model not found at:\n  {WAKEWORD_MODEL}")
    print("Run install.sh to check the correct path, then update WAKEWORD_MODEL in jarvis.py.")
    sys.exit(1)

oww = Model(wakeword_model_paths=[WAKEWORD_MODEL])

print(f"Loading Whisper ({WHISPER_MODEL})...")
whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

audio = pyaudio.PyAudio()

print("\n✓ Ready. Say 'Hey Jarvis' to begin.\n")


def record_after_wakeword():
    """Wait for speech to begin, then record until trailing silence.

    Returns None if the user never spoke. The caller must skip transcription
    in that case — Whisper hallucinates phrases like "Thank you." on silent
    audio, which would falsely trigger the exit phrase and end the chat.
    """
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
    speech_started = False
    silent_chunks = 0
    waited_chunks = 0
    speech_chunks = 0
    chunks_per_sec = DEVICE_RATE / CHUNK_SIZE
    max_wait_chunks = int(chunks_per_sec * SPEECH_WAIT_SECONDS)
    max_speech_chunks = int(chunks_per_sec * RECORD_SECONDS)
    silence_chunks_limit = int(chunks_per_sec * SILENCE_SECONDS)

    while True:
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        amplitude = np.abs(np.frombuffer(data, dtype=np.int16)).mean()

        if not speech_started:
            # Waiting for the user to start talking — don't count this
            # toward silence, and don't keep the (empty) audio.
            if amplitude >= SILENCE_THRESHOLD:
                speech_started = True
                frames.append(downsample(data, DEVICE_RATE, TARGET_RATE))
            else:
                waited_chunks += 1
                if waited_chunks >= max_wait_chunks:
                    break  # user never spoke
            continue

        frames.append(downsample(data, DEVICE_RATE, TARGET_RATE))
        speech_chunks += 1

        if amplitude < SILENCE_THRESHOLD:
            silent_chunks += 1
            if silent_chunks >= silence_chunks_limit:
                break  # trailing silence — user finished talking
        else:
            silent_chunks = 0

        if speech_chunks >= max_speech_chunks:
            break  # hit max recording length

    stream.stop_stream()
    stream.close()
    return frames if speech_started else None


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


# Explicit phrases (with the name) always end the conversation.
EXIT_PHRASES = (
    "thank you jarvis",
    "thanks jarvis",
    "goodbye jarvis",
    "bye jarvis",
    "stop jarvis",
)

# Whisper frequently drops the proper noun "Jarvis", so a SHORT standalone
# farewell also ends the chat. Kept short (<= MAX words) so a longer sentence
# like "thanks, that was really helpful and..." does NOT quit mid-conversation.
FAREWELL_STARTERS = ("thank you", "thanks", "thank you very much", "goodbye", "good bye", "bye")
FAREWELL_MAX_WORDS = 4


def is_exit_phrase(text):
    """True if the utterance is an exit command (name optional)."""
    cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
    cleaned = " ".join(cleaned.split())  # collapse whitespace
    if not cleaned:
        return False
    # 1) explicit "... jarvis" phrases
    if any(phrase in cleaned for phrase in EXIT_PHRASES):
        return True
    # 2) short standalone farewell (name may have been dropped by Whisper)
    words = cleaned.split()
    if len(words) <= FAREWELL_MAX_WORDS and any(
        cleaned.startswith(f) for f in FAREWELL_STARTERS
    ):
        return True
    return False


def send_to_hermes(text, continue_session=False):
    """Send transcribed text to Hermes CLI, print and speak response.

    continue_session=True adds -c so Hermes resumes its most recent session,
    keeping conversation memory across turns. The first turn omits it so each
    'Hey Jarvis' conversation starts a fresh session.
    """
    print(f"\nYou: {text}")
    print("Jarvis: ", end="", flush=True)

    cmd = ["hermes"]
    if continue_session:
        cmd.append("-c")
    cmd += ["-z", text]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=HERMES_TIMEOUT,
        )
        response = strip_ansi(result.stdout.strip() or result.stderr.strip())
    except subprocess.TimeoutExpired:
        response = "Sorry, I didn't get a response in time."
    except FileNotFoundError:
        response = "Hermes is not installed or not in PATH."

    print(response)
    print()

    if response:
        speak(response)


def conversation_loop():
    """Keep conversing until the user says the exit phrase."""
    print("🗣 Conversation mode — say 'Thank you Jarvis' to stop.\n")

    first_turn = True
    while True:
        try:
            frames = record_after_wakeword()

            if frames is None:
                # No speech within SPEECH_WAIT_SECONDS — assume the user
                # walked away. End the conversation instead of looping forever.
                print("\n(No speech detected — ending conversation.)")
                print("✓ Listening for 'Hey Jarvis'...\n")
                break

            text = transcribe(frames)

            if not text:
                print("(Nothing heard — still listening)\n")
                continue

            if is_exit_phrase(text):
                print("\nJarvis: You're welcome!")
                speak("You're welcome!")
                print("\n✓ Conversation ended. Listening for 'Hey Jarvis'...\n")
                break

            send_to_hermes(text, continue_session=not first_turn)
            first_turn = False

        except Exception as e:
            print(f"\n[Error] {e} — recovering...\n")


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

            for _, score in prediction.items():
                if score > WAKEWORD_THRESHOLD:
                    print(f"\n⚡ Wake word detected! (score: {score:.2f})")
                    stream.stop_stream()
                    stream.close()

                    conversation_loop()

                    # Reopen stream after conversation ends
                    stream = audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=DEVICE_RATE,
                        input=True,
                        input_device_index=DEVICE_INDEX,
                        frames_per_buffer=CHUNK_SIZE,
                    )
                    oww.reset()

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    listen_for_wakeword()
