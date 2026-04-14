#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DATA_DIR="$SCRIPT_DIR/data"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found. Run ./dev-setup.sh first." >&2
  exit 1
fi

mkdir -p "$DATA_DIR/results/rtd/raw"
mkdir -p "$DATA_DIR/results/rtd/reports"
mkdir -p "$DATA_DIR/results/ezdfs/raw"
mkdir -p "$DATA_DIR/results/ezdfs/reports"
mkdir -p "$DATA_DIR/logs"

cd "$SCRIPT_DIR"
"$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 10223
