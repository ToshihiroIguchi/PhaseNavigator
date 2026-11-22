#!/usr/bin/env bash
# Start the application using the project virtual environment.
# Usage: ./run.sh [--allow-non-commercial] [additional uvicorn arguments]
#   --allow-non-commercial  Make non-commercial (CC BY-NC, e.g. GNoME) data available
#                           as an opt-in option in the UI. Disabled by default.
set -euo pipefail

if [ "${1:-}" = "--allow-non-commercial" ]; then
  export ALLOW_NON_COMMERCIAL=1
  shift
fi

VENV_PYTHON="venv/bin/python"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Error: virtual environment not found. Run ./setup.sh first." >&2
  exit 1
fi

exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" "$@"
