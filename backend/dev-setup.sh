#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
DATA_DIR="$SCRIPT_DIR/data"
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

if [[ ! -d "$VENV_DIR" ]]; then
  if command -v uv >/dev/null 2>&1; then
    UV_CACHE_DIR="$UV_CACHE_DIR" uv venv "$VENV_DIR"
  else
    python3 -m venv "$VENV_DIR"
  fi
fi

if command -v uv >/dev/null 2>&1; then
  UV_CACHE_DIR="$UV_CACHE_DIR" uv pip install --python "$VENV_DIR/bin/python" -r "$SCRIPT_DIR/requirements.txt"
else
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

mkdir -p "$DATA_DIR/results/rtd/raw"
mkdir -p "$DATA_DIR/results/rtd/reports"
mkdir -p "$DATA_DIR/results/ezdfs/raw"
mkdir -p "$DATA_DIR/results/ezdfs/reports"
mkdir -p "$DATA_DIR/logs"

cat <<EOF
WSL backend development setup is ready.

Activate:
  source "$VENV_DIR/bin/activate"

Run:
  cd "$SCRIPT_DIR"
  uvicorn app.main:app --reload --host 0.0.0.0 --port 10223

Or use the helper:
  "$SCRIPT_DIR/run-dev.sh"

Data:
  DB      : $DATA_DIR/autotestmanager.db
  DB Web  : http://127.0.0.1:8080
  Results : $DATA_DIR/results
EOF
