#!/bin/bash
# Jarvis Voice Assistant - Installer
# Raspberry Pi 5 + Hermes + OpenWakeWord + Whisper

set -e  # Stop on any error

echo "================================================"
echo "  Jarvis Voice Assistant - Install Script"
echo "================================================"
echo ""

# ── 1. System dependencies ────────────────────────
echo "[1/5] Installing system dependencies..."
sudo apt update -q
sudo apt install -y portaudio19-dev
echo "      ✓ Done"

# ── 2. Python packages ────────────────────────────
echo "[2/5] Installing Python packages..."
pip install openwakeword faster-whisper pyaudio numpy --break-system-packages
echo "      ✓ Done"

# ── 3. Verify wake word model ─────────────────────
echo "[3/5] Checking wake word model..."
MODEL_PATH=~/.local/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx
if [ -f "$MODEL_PATH" ]; then
    echo "      ✓ hey_jarvis_v0.1.onnx found"
else
    echo "      ✗ Model not found at expected path: $MODEL_PATH"
    echo "      Run: ls ~/.local/lib/python*/site-packages/openwakeword/resources/models/"
    echo "      Then update WAKEWORD_MODEL in jarvis.py to match."
fi

# ── 4. Copy script to home directory ─────────────
echo "[4/5] Copying jarvis.py to home directory..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/jarvis.py" ~/jarvis.py
chmod +x ~/jarvis.py
echo "      ✓ Copied to ~/jarvis.py"

# ── 5. Audio device check ─────────────────────────
echo "[5/5] Audio devices detected:"
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
echo "  2. Make sure Hermes is installed and pointing"
echo "     at your LM Studio endpoint."
echo ""
echo "  3. Run Jarvis:"
echo "     python ~/jarvis.py"
echo ""
echo "  OPTIONAL - Auto-start on boot:"
echo "     bash install_service.sh"
echo "================================================"
