#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_FILE="$HOME/Library/LaunchAgents/com.batteryhealth.logger.plist"
DESKTOP_SHORTCUT="$HOME/Desktop/Battery Health Analyzer.command"
LOGGER_WRAPPER="$SCRIPT_DIR/run_battery_logger.sh"
ANALYZER_WRAPPER="$SCRIPT_DIR/open_battery_health_analyzer.command"

if command -v python3 >/dev/null 2>&1; then
	PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
	PYTHON_BIN="$(command -v python)"
else
	echo "Python 3 was not found in PATH."
	exit 1
fi

chmod +x "$LOGGER_WRAPPER" "$ANALYZER_WRAPPER"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>com.batteryhealth.logger</string>
	<key>ProgramArguments</key>
	<array>
		<string>$PYTHON_BIN</string>
		<string>$PROJECT_DIR/battery_logger.py</string>
		<string>--loop</string>
		<string>--interval-seconds</string>
		<string>60</string>
		<string>--output</string>
		<string>$PROJECT_DIR/battery_history.csv</string>
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>StandardOutPath</key>
	<string>$PROJECT_DIR/battery_logger.out.log</string>
	<key>StandardErrorPath</key>
	<string>$PROJECT_DIR/battery_logger.err.log</string>
</dict>
</plist>
EOF

if [ -d "$HOME/Desktop" ]; then
	cp "$ANALYZER_WRAPPER" "$DESKTOP_SHORTCUT"
	chmod +x "$DESKTOP_SHORTCUT"
fi

launchctl bootout "gui/$(id -u)" "$PLIST_FILE" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
launchctl kickstart -k "gui/$(id -u)/com.batteryhealth.logger"

echo "Installed LaunchAgent: $PLIST_FILE"
echo "Desktop shortcut: $DESKTOP_SHORTCUT"
