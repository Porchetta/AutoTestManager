#!/usr/bin/env bash
set -euo pipefail

# Build/install backend & frontend in a fully offline environment using
# artifacts created by offline-prep.sh (copy the ./offline directory).
# Requirements offline: python + pip, node + npm, docker (for building images).

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OFFLINE_DIR="${OFFLINE_DIR:-$ROOT_DIR/offline}"
PIP_DIR="$OFFLINE_DIR/pip-wheels"
NPM_CACHE="$OFFLINE_DIR/npm-cache"

if [[ ! -d "$PIP_DIR" ]]; then
  echo "[error] Missing $PIP_DIR; run offline-prep.sh online and copy ./offline" >&2
  exit 1
fi
if [[ ! -d "$NPM_CACHE" ]]; then
  echo "[error] Missing $NPM_CACHE; run offline-prep.sh online and copy ./offline" >&2
  exit 1
fi

cd "$ROOT_DIR/backend"
echo "[offline] Installing backend dependencies from wheels" >&2
python -m pip install --no-index --find-links "$PIP_DIR" -r requirements.txt

echo "[offline] Building backend image (no network)" >&2
docker build --network=none -t autotestmanager-backend:offline .

cd "$ROOT_DIR/frontend"
echo "[offline] Installing frontend packages from cache" >&2
npm ci --offline --cache "$NPM_CACHE"

echo "[offline] Building frontend image (no network)" >&2
docker build --network=none -t autotestmanager-frontend:offline .

echo "[offline] Done. Use ./offline-run.sh to start with prebuilt images or docker compose build if needed." >&2
