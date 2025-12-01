#!/usr/bin/env bash
set -euo pipefail

containers=(mss_db mss_backend mss_frontend)

missing=()
for container in "${containers[@]}"; do
  if ! docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
    missing+=("$container")
  fi
done

if [ ${#missing[@]} -ne 0 ]; then
  echo "The following containers are not running: ${missing[*]}" >&2
  echo "Please start all services (e.g., 'docker-compose up -d') before running this script." >&2
  exit 1
fi

echo "All containers are running. Opening shells sequentially."
for container in "${containers[@]}"; do
  echo "\nConnecting to $container (type 'exit' to move to the next container)..."
  docker exec -it "$container" /bin/bash || docker exec -it "$container" /bin/sh
done
