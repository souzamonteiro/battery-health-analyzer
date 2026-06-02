#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
SERVICE_FILE="/etc/systemd/system/battery-health-analyzer-logger.service"
LOGGER_WRAPPER="$SCRIPT_DIR/run_battery_logger.sh"
ANALYZER_WRAPPER="$SCRIPT_DIR/open_battery_health_analyzer.sh"
ICON_FILE="$PROJECT_DIR/assets/battery-health-analyzer.svg"

usage() {
	echo "Usage: $0 [--metric health|charge]"
}

normalize_metric_mode() {
	local raw_mode="$1"
	raw_mode="${raw_mode,,}"
	if [[ "$raw_mode" != "health" && "$raw_mode" != "charge" ]]; then
		echo "Invalid metric mode: '$1'. Expected 'health' or 'charge'."
		exit 1
	fi
	echo "$raw_mode"
}

service_metric_mode() {
	if [[ ! -f "$SERVICE_FILE" ]]; then
		return 1
	fi

	local existing_mode
	existing_mode="$(grep -E '^Environment=BATTERY_LOGGER_METRIC=' "$SERVICE_FILE" | tail -n 1 | cut -d'=' -f3- || true)"
	if [[ -z "$existing_mode" ]]; then
		return 1
	fi

	normalize_metric_mode "$existing_mode"
}

TARGET_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
if [[ -z "$TARGET_HOME" ]]; then
	TARGET_HOME="$HOME"
fi

APP_DIR="$TARGET_HOME/.local/share/applications"
APP_FILE="$APP_DIR/battery-health-analyzer.desktop"
DESKTOP_FILE="$TARGET_HOME/Desktop/Battery Health Analyzer.desktop"

CLI_METRIC_MODE=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--metric)
			if [[ $# -lt 2 ]]; then
				echo "Missing value for --metric"
				usage
				exit 1
			fi
			CLI_METRIC_MODE="$2"
			shift 2
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown argument: $1"
			usage
			exit 1
			;;
	esac
	done

if [[ -n "$CLI_METRIC_MODE" ]]; then
	METRIC_MODE="$(normalize_metric_mode "$CLI_METRIC_MODE")"
elif [[ -n "${BATTERY_LOGGER_METRIC:-}" ]]; then
	METRIC_MODE="$(normalize_metric_mode "$BATTERY_LOGGER_METRIC")"
elif EXISTING_METRIC_MODE="$(service_metric_mode)"; then
	METRIC_MODE="$EXISTING_METRIC_MODE"
else
	METRIC_MODE="health"
fi

if ! command -v systemctl >/dev/null 2>&1; then
	echo "systemd/systemctl was not found. This installer expects a systemd-based Linux distribution."
	exit 1
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
	echo "Python 3 was not found in PATH."
	exit 1
fi

if [[ ${EUID:-$(id -u)} -eq 0 && -n "${SUDO_USER:-}" && -z "${BATTERY_LOGGER_METRIC:-}" && -z "$CLI_METRIC_MODE" ]]; then
	echo "Note: running via sudo can drop exported BATTERY_LOGGER_METRIC from your shell."
	echo "      Use '--metric charge' (preferred) or 'sudo BATTERY_LOGGER_METRIC=charge $0'."
	echo "      No explicit metric was provided, so installer preserved existing service mode: $METRIC_MODE"
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
Environment=BATTERY_LOGGER_METRIC=$METRIC_MODE
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
echo "Logger metric mode: $METRIC_MODE"
echo "Installed analyzer launcher: $APP_FILE"
echo "Optional desktop shortcut: $DESKTOP_FILE"
