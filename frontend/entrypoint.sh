#!/bin/sh
set -e

MODE="${ATM_MODE:-${1:-dev}}"

if [ "$MODE" = "prod" ]; then
  echo "[atm-frontend] Production mode: building dist and serving with nginx"
  VITE_API_BASE_URL="${VITE_API_BASE_URL:-}" npm run build
  exec nginx -g "daemon off;"
else
  echo "[atm-frontend] Development mode: Vite dev server (HMR)"
  exec npm run dev
fi
