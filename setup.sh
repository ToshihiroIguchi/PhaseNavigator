#!/usr/bin/env bash
# Create (or refresh) the project virtual environment and install dependencies.
#
# Usage:
#   ./setup.sh                     # create venv and install requirements
#   ./setup.sh --with-pmg-addons   # also build the optional pymatgen add-ons
#   PYTHON_BIN=python3.13 ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="venv"
WITH_PMG_ADDONS=0

for arg in "$@"; do
  case "$arg" in
    --with-pmg-addons) WITH_PMG_ADDONS=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: '$PYTHON_BIN' not found. Install Python 3.11 or newer." >&2
  exit 1
fi

# pymatgen, mp-api and emmet-core require Python 3.11 or newer.
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"Error: Python 3.11+ is required, found {sys.version.split()[0]}.")
PY

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in ./$VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
echo "Installing dependencies with $VENV_PYTHON ..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt

# The optional pymatgen add-ons (enumlib, bader) are not used by the phase diagram
# pipeline. They need a Fortran toolchain, so they are opt-in.
if [ "$WITH_PMG_ADDONS" -eq 1 ]; then
  for addon in enumlib bader; do
    echo "Installing optional pymatgen add-on: $addon ..."
    "$VENV_DIR/bin/pmg" config --install "$addon" || echo "Warning: 'pmg config --install $addon' failed; continuing."
  done
fi

echo
echo "Done. Use the wrapper scripts, or activate the environment with:"
echo "  source $VENV_DIR/bin/activate"
