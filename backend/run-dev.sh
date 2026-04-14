#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found. Run ./dev-setup.sh first." >&2
  exit 1
fi

cd "$SCRIPT_DIR"
"$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 10223
