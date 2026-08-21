#!/usr/bin/env bash
# Start the application using the project virtual environment.
# Usage: ./run.sh [additional uvicorn arguments]
set -euo pipefail

VENV_PYTHON="venv/bin/python"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Error: virtual environment not found. Run ./setup.sh first." >&2
  exit 1
fi

exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" "$@"
