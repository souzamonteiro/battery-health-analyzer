#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_WRAPPER="$SCRIPT_DIR/run_battery_web_service.sh"
PLIST_NAME="com.batteryhealth.webservice"
PLIST_FILE="/Library/LaunchDaemons/$PLIST_NAME.plist"

usage() {
  echo "Usage: sudo $0 [--port <port>]"
}

PORT_VALUE="${PORT:-8000}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --port"
        usage
        exit 1
      fi
      PORT_VALUE="$2"
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

if [[ $(id -u) -ne 0 ]]; then
  echo "This installer must run as root (use sudo)."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js was not found in PATH."
  exit 1
fi

chmod +x "$SERVER_WRAPPER"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_NAME</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SERVER_WRAPPER</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PORT</key>
    <string>$PORT_VALUE</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$PROJECT_DIR/server.out.log</string>
  <key>StandardErrorPath</key>
  <string>$PROJECT_DIR/server.err.log</string>
</dict>
</plist>
EOF

chmod 644 "$PLIST_FILE"
chown root:wheel "$PLIST_FILE"

launchctl bootout system "$PLIST_FILE" >/dev/null 2>&1 || true
launchctl bootstrap system "$PLIST_FILE"
launchctl kickstart -k "system/$PLIST_NAME"

echo "Installed optional web service LaunchDaemon: $PLIST_FILE"
echo "Port: $PORT_VALUE"
echo "Status: sudo launchctl print system/$PLIST_NAME"
