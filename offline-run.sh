#!/usr/bin/env bash
set -euo pipefail

# Example offline runner for prebuilt images.
# Expected tarballs (adjust with env vars):
#   FRONTEND_TAR=./images/frontend.tar
#   BACKEND_TAR=./images/backend.tar
#   DB_TAR=./images/db.tar (e.g., mysql:8.0 saved online)
# Image tags can also be overridden (FRONTEND_IMAGE/BACKEND_IMAGE/DB_IMAGE).

FRONTEND_TAR=${FRONTEND_TAR:-./images/frontend.tar}
BACKEND_TAR=${BACKEND_TAR:-./images/backend.tar}
DB_TAR=${DB_TAR:-./images/db.tar}

FRONTEND_IMAGE=${FRONTEND_IMAGE:-mss-frontend:offline}
BACKEND_IMAGE=${BACKEND_IMAGE:-mss-backend:offline}
DB_IMAGE=${DB_IMAGE:-mysql:8.0}

load_image() {
  local tar_path="$1"
  local target_image="$2"
  if [[ -f "$tar_path" ]]; then
    echo "Loading $tar_path ..."
    loaded_image=$(docker load -i "$tar_path" | sed -n 's/^Loaded image: \(.*\)/\1/p')
    if [[ -n "$loaded_image" && "$loaded_image" != "$target_image" ]]; then
      echo "Tagging $loaded_image as $target_image"
      docker tag "$loaded_image" "$target_image"
    fi
  else
    echo "[WARN] $tar_path not found, skipping load for $target_image"
  fi
}

load_image "$FRONTEND_TAR" "$FRONTEND_IMAGE"
load_image "$BACKEND_TAR" "$BACKEND_IMAGE"
load_image "$DB_TAR" "$DB_IMAGE"

docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d "$@"
