#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_FILE="${1:-$PROJECT_DIR/battery_history.csv}"
INTERVAL_SECONDS="${BATTERY_LOGGER_INTERVAL_SECONDS:-60}"

if command -v python3 >/dev/null 2>&1; then
	PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
	PYTHON_BIN="python"
else
	echo "Python 3 was not found in PATH."
	exit 1
fi

exec "$PYTHON_BIN" "$PROJECT_DIR/battery_logger.py" --loop --interval-seconds "$INTERVAL_SECONDS" --output "$OUTPUT_FILE"
