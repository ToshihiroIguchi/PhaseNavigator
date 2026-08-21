#!/usr/bin/env bash
# Run the test suite using the project virtual environment.
# Usage: ./test.sh [additional pytest arguments]
set -euo pipefail

VENV_PYTHON="venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Error: virtual environment not found. Run ./setup.sh first." >&2
  exit 1
fi

exec "$VENV_PYTHON" -m pytest "$@"
