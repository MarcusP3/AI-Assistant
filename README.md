# Jarvis Voice Assistant

A locally-running voice assistant for Raspberry Pi 5. Say "Hey Jarvis", ask a question, and get a spoken response — no cloud required (except your LLM backend).

## How It Works

1. **Wake word** — Jarvis listens continuously for "Hey Jarvis" using [OpenWakeWord](https://github.com/dscripka/openWakeWord)
2. **Record** — After the wake word, it records your voice until you stop speaking
3. **Transcribe** — [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) converts your speech to text locally on the Pi
4. **Think** — The text is sent to [Hermes Agent](https://hermes-agent.nousresearch.com) which queries your LLM (LM Studio running on a separate machine)
5. **Speak** — The response is spoken back using [Piper TTS](https://github.com/rhasspy/piper) locally on the Pi

## Requirements

- Raspberry Pi 5
- USB microphone/speaker (or USB-C audio device)
- A separate machine running [LM Studio](https://lmstudio.ai) with the local server enabled (tested on NVIDIA DGX Spark)

## Installation

```bash
git clone https://github.com/MarcusP3/AI-Assistant.git
cd AI-Assistant
bash install.sh
```

The install script handles everything:
- System dependencies
- Python packages (OpenWakeWord, Faster Whisper, PyAudio, NumPy)
- Hermes Agent CLI
- Piper TTS + voice model
- Points Hermes at your LM Studio instance

## Running Jarvis

```bash
python ~/jarvis.py
```

Say **"Hey Jarvis"** to wake it up.

## Auto-start on Boot (Optional)

```bash
bash install_service.sh
```

Useful commands after that:
```bash
systemctl --user status jarvis    # check if running
systemctl --user restart jarvis   # restart
journalctl --user -u jarvis -f    # view live logs
```

## Configuration

Key settings at the top of `jarvis.py`:

| Variable | Default | Description |
|---|---|---|
| `DEVICE_INDEX` | `1` | PyAudio index of your mic — run `install.sh` to see your devices |
| `DEVICE_RATE` | `48000` | Sample rate of your audio device |
| `WAKEWORD_THRESHOLD` | `0.5` | Wake word sensitivity (0.0–1.0) |
| `WHISPER_MODEL` | `tiny` | Whisper model size — `tiny` is fastest on Pi |
| `PIPER_VOICE` | `en_US-lessac-medium` | TTS voice model |

## Dependencies

- [OpenWakeWord](https://github.com/dscripka/openWakeWord) — wake word detection
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) — speech-to-text
- [PyAudio](https://pypi.org/project/PyAudio/) — audio capture
- [Hermes Agent](https://hermes-agent.nousresearch.com) — AI agent CLI
- [Piper TTS](https://github.com/rhasspy/piper) — text-to-speech
- [LM Studio](https://lmstudio.ai) — LLM backend (runs on separate machine)

---

> **Disclaimer:** This project is vibe-coded. It works on my setup and probably yours, but don't expect production-grade error handling. If it breaks, that's part of the experience. Thank you for your understanding.
