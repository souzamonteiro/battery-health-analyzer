#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

NODE_BIN="${NODE_BIN:-}"
NPM_BIN="${NPM_BIN:-}"

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
  echo "Node.js was not found. Set NODE_BIN or ensure node is in PATH."
  exit 1
fi

if [[ -z "$NPM_BIN" ]] || [[ ! -x "$NPM_BIN" ]]; then
  echo "npm was not found. Set NPM_BIN or ensure npm is in PATH."
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -d "$PROJECT_DIR/node_modules" ]]; then
  echo "Installing Node.js dependencies..."
  "$NPM_BIN" install
fi

exec "$NPM_BIN" start
