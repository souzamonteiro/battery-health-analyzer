#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
APP_DIR="$HOME/.local/share/applications"
APP_FILE="$APP_DIR/battery-health-analyzer.desktop"
DESKTOP_FILE="$HOME/Desktop/Battery Health Analyzer.desktop"
SERVICE_FILE="/etc/systemd/system/battery-health-analyzer-logger.service"
LOGGER_WRAPPER="$SCRIPT_DIR/run_battery_logger.sh"
ANALYZER_WRAPPER="$SCRIPT_DIR/open_battery_health_analyzer.sh"
ICON_FILE="$PROJECT_DIR/assets/battery-health-analyzer.svg"

if ! command -v systemctl >/dev/null 2>&1; then
	echo "systemd/systemctl was not found. This installer expects a systemd-based Linux distribution."
	exit 1
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
	echo "Python 3 was not found in PATH."
	exit 1
fi

chmod +x "$LOGGER_WRAPPER" "$ANALYZER_WRAPPER"
mkdir -p "$APP_DIR"

cat > "$APP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Battery Health Analyzer
Comment=Open Battery Health Analyzer with the default history file
Exec=$ANALYZER_WRAPPER
Icon=$ICON_FILE
Terminal=false
Categories=Utility;Science;
EOF
chmod +x "$APP_FILE"

if [ -d "$HOME/Desktop" ]; then
	cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Battery Health Analyzer
Comment=Open Battery Health Analyzer with the default history file
Exec=$ANALYZER_WRAPPER
Icon=$ICON_FILE
Terminal=false
Categories=Utility;Science;
EOF
	chmod +x "$DESKTOP_FILE"
fi

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Battery Health Analyzer logger
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$LOGGER_WRAPPER
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now battery-health-analyzer-logger.service

echo "Installed logger service: battery-health-analyzer-logger.service"
echo "Installed analyzer launcher: $APP_FILE"
echo "Optional desktop shortcut: $DESKTOP_FILE"
