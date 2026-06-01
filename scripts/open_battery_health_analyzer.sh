#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_BDF_FILE="$PROJECT_DIR/battery_data.bdf.csv"
INPUT_FILE="${1:-$DEFAULT_BDF_FILE}"

if command -v python3 >/dev/null 2>&1; then
	PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
	PYTHON_BIN="python"
else
	echo "Python 3 was not found in PATH."
	exit 1
fi

if [[ -f "$INPUT_FILE" ]]; then
	exec "$PYTHON_BIN" "$PROJECT_DIR/battery_bdf_analyzer.py" "$INPUT_FILE"
fi

exec "$PYTHON_BIN" "$PROJECT_DIR/battery_bdf_analyzer.py"
