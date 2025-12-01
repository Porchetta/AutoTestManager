#!/usr/bin/env bash
set -euo pipefail

# Prepare offline artifacts (run **online**).
# - Downloads Python wheels for backend requirements into ./offline/pip-wheels
# - Pre-fills an npm cache for the frontend into ./offline/npm-cache
# - Saves Docker images (optional) if you still want offline-run.sh flow
#
# Requirements: python + pip, node + npm, docker (for optional saves)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OFFLINE_DIR="$ROOT_DIR/offline"
PIP_DIR="$OFFLINE_DIR/pip-wheels"
NPM_CACHE="$OFFLINE_DIR/npm-cache"
IMAGES_DIR="$OFFLINE_DIR/images"

mkdir -p "$PIP_DIR" "$NPM_CACHE" "$IMAGES_DIR"

cd "$ROOT_DIR/backend"
echo "[prep] Downloading backend Python wheels to $PIP_DIR" >&2
python -m pip download --requirement requirements.txt --dest "$PIP_DIR"

cd "$ROOT_DIR/frontend"
echo "[prep] Populating frontend npm cache at $NPM_CACHE" >&2
npm ci --cache "$NPM_CACHE" --prefer-offline --registry="https://registry.npmjs.org"

echo "[prep] (optional) Save images for offline-run.sh by building first, then:"
echo "  docker save autotestmanager-frontend:latest -o $IMAGES_DIR/frontend.tar" >&2
echo "  docker save autotestmanager-backend:latest  -o $IMAGES_DIR/backend.tar" >&2
echo "  docker save mysql:8.0 -o $IMAGES_DIR/db.tar" >&2
