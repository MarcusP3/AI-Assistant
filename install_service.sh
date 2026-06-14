#!/bin/bash
# Jarvis - Auto-start on Boot (systemd service)

echo "Setting up Jarvis as a systemd service..."

mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jarvis.service << 'EOF'
[Unit]
Description=Jarvis Voice Assistant
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/%u/jarvis.py
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
