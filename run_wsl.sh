#!/usr/bin/env bash
# ==============================================================================
# Job Search Monitor - Daily Runner for WSL / Linux
# ==============================================================================
set -e

# Resolve script directory (even if called from another working directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present
if [ -d "$SCRIPT_DIR/venv" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Determine python command
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "[ERROR] Python was not found in WSL. Please install python3 (sudo apt install python3 python3-pip)." >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Job Search Monitor from WSL..."
"$PY_CMD" main.py --once "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Job Search Monitor completed successfully."

