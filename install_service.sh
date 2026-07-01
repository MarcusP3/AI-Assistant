#!/bin/bash
# Jarvis - Auto-start on Boot (systemd service)

echo "Setting up Jarvis as a systemd service..."

mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jarvis.service << 'EOF'
[Unit]
Description=Jarvis Voice Assistant
After=network.target

[Service]
ExecStart=/usr/bin/python3 %h/jarvis.py
# hermes lives in ~/.hermes/bin and piper/aplay in ~/.local/bin; the default
# systemd env has neither, so add them or the assistant can't reach its LLM.
Environment=PATH=%h/.hermes/bin:%h/.local/bin:/usr/local/bin:/usr/bin:/bin
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user enable jarvis.service
systemctl --user start jarvis.service

echo "✓ Jarvis service installed and started."
echo ""
echo "Useful commands:"
echo "  systemctl --user status jarvis   # check if running"
echo "  systemctl --user stop jarvis     # stop it"
echo "  systemctl --user restart jarvis  # restart it"
echo "  journalctl --user -u jarvis -f   # view live logs"
