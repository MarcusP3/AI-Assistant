#!/bin/bash
# Jarvis Voice Assistant - Installer
# Raspberry Pi 5 + Hermes + OpenWakeWord + Whisper

set -e  # Stop on any error

echo "================================================"
echo "  Jarvis Voice Assistant - Install Script"
echo "================================================"
echo ""

# ── 1. System dependencies ────────────────────────
echo "[1/6] Installing system dependencies..."
sudo apt update -q
sudo apt install -y portaudio19-dev curl
echo "      ✓ Done"

# ── 2. Python packages ────────────────────────────
echo "[2/6] Installing Python packages..."
pip install openwakeword faster-whisper pyaudio numpy --break-system-packages
echo "      ✓ Done"

# ── 3. Install Hermes Agent ───────────────────────
echo "[3/6] Installing Hermes Agent..."
if command -v hermes &> /dev/null; then
    echo "      ✓ Hermes already installed ($(hermes --version 2>/dev/null || echo 'version unknown'))"
else
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    # Reload shell config to get hermes in PATH
    export PATH="$HOME/.hermes/bin:$PATH"
    echo "      ✓ Hermes installed"
fi

# ── 4. Configure Hermes → LM Studio on DGX Spark ─
echo "[4/6] Configuring Hermes..."
echo ""
echo "  Enter your DGX Spark's IP address"
echo "  (find it by running 'ipconfig' on the DGX Spark,"
echo "   look for IPv4 address, e.g. 192.168.1.50)"
echo ""
read -p "  DGX Spark IP: " DGX_IP

if [ -n "$DGX_IP" ]; then
    mkdir -p ~/.hermes
    # Set LM Studio endpoint
    hermes config set LM_BASE_URL "http://${DGX_IP}:1234/v1"
    echo "      ✓ Hermes pointed at http://${DGX_IP}:1234/v1"
    echo "      Note: Make sure LM Studio is running on the DGX Spark"
    echo "      with the local server enabled (port 1234)."
else
    echo "      ⚠ Skipped — run manually later:"
    echo "      hermes config set LM_BASE_URL http://<DGX_IP>:1234/v1"
    echo "      hermes model"
fi

# ── 5. Install Piper TTS ─────────────────────────
echo "[5/7] Installing Piper TTS..."
PIPER_DIR=~/.local/bin
PIPER_VOICE_DIR=~/.local/share/piper
mkdir -p "$PIPER_DIR" "$PIPER_VOICE_DIR"

if [ -f "$PIPER_DIR/piper" ]; then
    echo "      ✓ Piper already installed"
else
    # Download latest Piper for arm64 (Pi 5)
    PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz"
    echo "      Downloading Piper..."
    curl -L "$PIPER_URL" | tar -xz -C /tmp/
    cp /tmp/piper/piper "$PIPER_DIR/piper"
    chmod +x "$PIPER_DIR/piper"
    echo "      ✓ Piper installed to $PIPER_DIR/piper"
fi

# Download voice model if not present
VOICE_MODEL="$PIPER_VOICE_DIR/en_US-lessac-medium.onnx"
VOICE_CONFIG="$PIPER_VOICE_DIR/en_US-lessac-medium.onnx.json"
if [ -f "$VOICE_MODEL" ]; then
    echo "      ✓ Voice model already present"
else
    echo "      Downloading voice model (en_US-lessac-medium)..."
    VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
    curl -L "$VOICE_BASE/en_US-lessac-medium.onnx" -o "$VOICE_MODEL"
    curl -L "$VOICE_BASE/en_US-lessac-medium.onnx.json" -o "$VOICE_CONFIG"
    echo "      ✓ Voice model downloaded"
fi

# ── 6. Verify wake word model ─────────────────────
echo ""
echo "[6/7] Checking wake word model..."
MODEL_PATH=~/.local/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx
if [ -f "$MODEL_PATH" ]; then
    echo "      ✓ hey_jarvis_v0.1.onnx found"
else
    echo "      ✗ Model not found at expected path: $MODEL_PATH"
    echo "      Run: ls ~/.local/lib/python*/site-packages/openwakeword/resources/models/"
    echo "      Then update WAKEWORD_MODEL in jarvis.py to match."
fi

# ── 6. Copy script + audio device check ──────────
echo "[7/7] Copying jarvis.py to home directory..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/jarvis.py" ~/jarvis.py
chmod +x ~/jarvis.py
echo "      ✓ Copied to ~/jarvis.py"
echo ""
echo "  -- ALSA capture devices (arecord -l) --"
arecord -l 2>/dev/null || echo "      (no devices found)"
echo ""
echo "  -- PyAudio device indices --"
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(f'      Index {i}: {d[\"name\"]} (inputs: {d[\"maxInputChannels\"]})')
p.terminate()
" 2>/dev/null || echo "      (could not list PyAudio devices)"

echo ""
echo "================================================"
echo "  Install complete!"
echo ""
echo "  NEXT STEPS:"
echo "  1. Check the device list above."
echo "     If your mic index is NOT 1, edit jarvis.py"
echo "     and change DEVICE_INDEX to match."
echo ""
echo "  2. Set your Hermes model:"
echo "     hermes model"
echo "     (select LM Studio from the list)"
echo ""
echo "  3. Run Jarvis:"
echo "     python ~/jarvis.py"
echo ""
echo "  OPTIONAL - Auto-start on boot:"
echo "     bash install_service.sh"
echo "================================================"
