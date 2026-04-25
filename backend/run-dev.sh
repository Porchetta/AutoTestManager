#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DATA_DIR="$SCRIPT_DIR/data"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found. Run ./dev-setup.sh first." >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/sqlite_web" ]]; then
  echo "sqlite-web is not installed. Run ./dev-setup.sh first." >&2
  exit 1
fi

read_env_value() {
  local key="$1"
  if [[ -f "$ENV_FILE" ]]; then
    awk -F= -v key="$key" '
      $1 == key {
        sub(/^[^=]*=/, "")
        gsub(/^["'\'']|["'\'']$/, "")
        print
        exit
      }
    ' "$ENV_FILE"
  fi
}

DB_PATH="${DB_PATH:-$(read_env_value DB_PATH)}"
DB_PATH="${DB_PATH:-$DATA_DIR/autotestmanager.db}"
BACKEND_PORT="${BACKEND_PORT:-$(read_env_value BACKEND_PORT)}"
BACKEND_PORT="${BACKEND_PORT:-10223}"
SQLITE_WEB_ENABLED="${SQLITE_WEB_ENABLED:-$(read_env_value SQLITE_WEB_ENABLED)}"
SQLITE_WEB_ENABLED="${SQLITE_WEB_ENABLED:-1}"
SQLITE_WEB_HOST="${SQLITE_WEB_HOST:-$(read_env_value SQLITE_WEB_HOST)}"
SQLITE_WEB_HOST="${SQLITE_WEB_HOST:-0.0.0.0}"
SQLITE_WEB_PORT="${SQLITE_WEB_PORT:-$(read_env_value SQLITE_WEB_PORT)}"
SQLITE_WEB_PORT="${SQLITE_WEB_PORT:-8080}"
SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY:-$(read_env_value SQLITE_WEB_READ_ONLY)}"
SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY:-0}"

mkdir -p "$DATA_DIR/results/rtd/raw"
mkdir -p "$DATA_DIR/results/rtd/reports"
mkdir -p "$DATA_DIR/results/ezdfs/raw"
mkdir -p "$DATA_DIR/results/ezdfs/reports"
mkdir -p "$DATA_DIR/logs"
mkdir -p "$(dirname "$DB_PATH")"
touch "$DB_PATH"

cd "$SCRIPT_DIR"

cleanup() {
  if [[ -n "${SQLITE_WEB_PID:-}" ]]; then
    kill "$SQLITE_WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "$SQLITE_WEB_ENABLED" == "1" ]]; then
  SQLITE_WEB_ARGS=("--host=$SQLITE_WEB_HOST" "--port=$SQLITE_WEB_PORT" "--no-browser")
  if [[ "$SQLITE_WEB_READ_ONLY" == "1" ]]; then
    SQLITE_WEB_ARGS+=("--read-only")
  fi

  "$VENV_DIR/bin/sqlite_web" "${SQLITE_WEB_ARGS[@]}" "$DB_PATH" &
  SQLITE_WEB_PID=$!
  echo "SQLite Web: http://127.0.0.1:${SQLITE_WEB_PORT} (DB: $DB_PATH)"
fi

echo "Backend: http://127.0.0.1:${BACKEND_PORT}"
"$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT"
