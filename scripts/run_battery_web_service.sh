#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_HOME="${HOME:-$(getent passwd "$(id -un)" | cut -d: -f6)}"
NVM_DIR="${NVM_DIR:-$USER_HOME/.nvm}"

NODE_BIN="${NODE_BIN:-}"
NPM_BIN="${NPM_BIN:-}"

load_nvm_if_available() {
  local nvm_sh="$NVM_DIR/nvm.sh"
  if [[ -f "$nvm_sh" ]]; then
    # shellcheck disable=SC1090
    source "$nvm_sh"
    nvm use --silent default >/dev/null 2>&1 || true
    return 0
  fi
  return 1
}

if [[ -z "$NODE_BIN" ]] || [[ ! -x "$NODE_BIN" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
  fi
fi

if [[ -z "$NPM_BIN" ]] || [[ ! -x "$NPM_BIN" ]]; then
  if command -v npm >/dev/null 2>&1; then
    NPM_BIN="$(command -v npm)"
  fi
fi

if [[ -z "$NODE_BIN" ]] || [[ ! -x "$NODE_BIN" ]]; then
  if load_nvm_if_available && command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
  fi
fi

if [[ -z "$NPM_BIN" ]] || [[ ! -x "$NPM_BIN" ]]; then
  if load_nvm_if_available && command -v npm >/dev/null 2>&1; then
    NPM_BIN="$(command -v npm)"
  fi
fi

if [[ -z "$NODE_BIN" ]] || [[ ! -x "$NODE_BIN" ]]; then
  echo "Node.js was not found. Set NODE_BIN or ensure node is in PATH/NVM_DIR ($NVM_DIR)."
  exit 1
fi

export PATH="$(dirname "$NODE_BIN"):$PATH"

cd "$PROJECT_DIR"

if [[ ! -d "$PROJECT_DIR/node_modules" ]]; then
  if [[ -n "$NPM_BIN" ]] && [[ -x "$NPM_BIN" ]]; then
    echo "Installing Node.js dependencies..."
    "$NPM_BIN" install
  else
    echo "node_modules is missing and npm was not found. Set NPM_BIN or ensure npm is in PATH/NVM_DIR ($NVM_DIR)."
    exit 1
  fi
fi

exec "$NODE_BIN" "$PROJECT_DIR/server.js"
