#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
SERVICE_NAME="battery-health-analyzer-web.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
SERVER_WRAPPER="$SCRIPT_DIR/run_battery_web_service.sh"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"

usage() {
  echo "Usage: $0 [--port <http_port>] [--ssl-port <https_port>]"
}

PORT_VALUE="${PORT:-9095}"
SSL_PORT_VALUE="${SSL_PORT:-9543}"
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
    --ssl-port)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --ssl-port"
        usage
        exit 1
      fi
      SSL_PORT_VALUE="$2"
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

if [[ "$PORT_VALUE" == "$SSL_PORT_VALUE" ]]; then
  echo "Invalid configuration: --port and --ssl-port cannot be the same value ($PORT_VALUE)."
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd/systemctl was not found. This installer expects a systemd-based Linux distribution."
  exit 1
fi

if [[ -z "$USER_HOME" ]]; then
  USER_HOME="$HOME"
fi

resolve_user_tool() {
  local tool_name="$1"
  if sudo -u "$USER_NAME" bash -lc "command -v $tool_name >/dev/null 2>&1"; then
    sudo -u "$USER_NAME" bash -lc "command -v $tool_name"
    return 0
  fi

  local nvm_sh="$USER_HOME/.nvm/nvm.sh"
  if [[ -f "$nvm_sh" ]]; then
    if sudo -u "$USER_NAME" bash -lc "export NVM_DIR=\"$USER_HOME/.nvm\"; source \"$nvm_sh\"; command -v $tool_name >/dev/null 2>&1"; then
      sudo -u "$USER_NAME" bash -lc "export NVM_DIR=\"$USER_HOME/.nvm\"; source \"$nvm_sh\"; command -v $tool_name"
      return 0
    fi
  fi

  return 1
}

if ! NODE_BIN="$(resolve_user_tool node)"; then
  echo "Node.js was not found for user '$USER_NAME' (including nvm at $USER_HOME/.nvm)."
  exit 1
fi

if ! NPM_BIN="$(resolve_user_tool npm)"; then
  echo "npm was not found for user '$USER_NAME' (including nvm at $USER_HOME/.nvm)."
  exit 1
fi

NODE_DIR="$(dirname "$NODE_BIN")"
SYSTEM_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
if [[ ":$SYSTEM_PATH:" != *":$NODE_DIR:"* ]]; then
  SERVICE_PATH="$NODE_DIR:$SYSTEM_PATH"
else
  SERVICE_PATH="$SYSTEM_PATH"
fi

chmod +x "$SERVER_WRAPPER"

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Battery Health Analyzer web service (Node.js)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Environment=HOME=$USER_HOME
Environment=NVM_DIR=$USER_HOME/.nvm
Environment=PORT=$PORT_VALUE
Environment=SSL_PORT=$SSL_PORT_VALUE
Environment=ENABLE_SSL=true
Environment=NODE_BIN=$NODE_BIN
Environment=NPM_BIN=$NPM_BIN
Environment=PATH=$SERVICE_PATH
WorkingDirectory=$PROJECT_DIR
ExecStart=$SERVER_WRAPPER
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "Installed optional web service: $SERVICE_NAME"
echo "HTTP Port:  $PORT_VALUE"
echo "HTTPS Port: $SSL_PORT_VALUE"
echo "Node: $NODE_BIN"
echo "npm:  $NPM_BIN"
echo "Status: systemctl status $SERVICE_NAME"
