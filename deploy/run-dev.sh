#!/usr/bin/env bash
set -euo pipefail

# 개발 모드 실행
# - Backend: uvicorn --reload (소스 변경 자동 반영)
# - Frontend: Vite dev server HMR (소스 변경 자동 반영)
# - Backend 포트 10223, Frontend 포트 4203 모두 외부 노출
#
# Usage: ./deploy/run-dev.sh [IMAGE_VERSION]
# IMAGE_VERSION 생략 시 latest 사용

BASE_DIR="/home/hyun/develope/AutoTestManager"
BACKEND_DATA_DIR="${BASE_DIR}/backend/data"
VERSION="${1:-latest}"
SERVER_IP="$(hostname -I | awk '{print $1}')"
BACKEND_API_URL="http://${SERVER_IP}:10223"
BACKEND_DEBUG_PORT="${BACKEND_DEBUG_PORT:-5678}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

if [[ ! -f "${BASE_DIR}/backend.env" ]]; then
  echo "ERROR: ${BASE_DIR}/backend.env not found."
  echo "Run ./deploy/setup.sh first."
  exit 1
fi

read_env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=/, "")
      gsub(/^["'\'']|["'\'']$/, "")
      print
      exit
    }
  ' "${BASE_DIR}/backend.env"
}

SQLITE_WEB_PORT="${SQLITE_WEB_PORT:-$(read_env_value SQLITE_WEB_PORT)}"
SQLITE_WEB_PORT="${SQLITE_WEB_PORT:-8080}"
SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY:-$(read_env_value SQLITE_WEB_READ_ONLY)}"
SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY:-0}"

echo "=== Stopping existing containers ==="
docker stop atm-backend atm-frontend 2>/dev/null || true
docker rm   atm-backend atm-frontend 2>/dev/null || true

echo ""
echo "=== Starting backend (dev, --reload) ==="
echo "    container user: ${HOST_UID}:${HOST_GID}"
echo "    debugpy port  : ${BACKEND_DEBUG_PORT}"
echo "    sqlite-web    : ${SQLITE_WEB_PORT}"
echo "    db read-only  : ${SQLITE_WEB_READ_ONLY}"
docker run -d \
  --name atm-backend \
  --network atm-net \
  --restart unless-stopped \
  --user "${HOST_UID}:${HOST_GID}" \
  -p 10223:10223 \
  -p "${SQLITE_WEB_PORT}:${SQLITE_WEB_PORT}" \
  -p "${BACKEND_DEBUG_PORT}:${BACKEND_DEBUG_PORT}" \
  -v "${BASE_DIR}/backend/app:/app/app" \
  -v "${BACKEND_DATA_DIR}:/data" \
  -e BACKEND_DEBUG_PORT="${BACKEND_DEBUG_PORT}" \
  -e SQLITE_WEB_PORT="${SQLITE_WEB_PORT}" \
  -e SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY}" \
  --env-file "${BASE_DIR}/backend.env" \
  atm-backend:"${VERSION}" \
  sh -c 'touch "${DB_PATH:-/data/autotestmanager.db}"; readonly_arg=""; if [ "${SQLITE_WEB_READ_ONLY:-0}" = "1" ]; then readonly_arg="--read-only"; fi; sqlite_web --host=0.0.0.0 --port="${SQLITE_WEB_PORT:-8080}" --no-browser ${readonly_arg} "${DB_PATH:-/data/autotestmanager.db}" & exec python -m debugpy --listen "0.0.0.0:${BACKEND_DEBUG_PORT}" -m uvicorn app.main:app --host 0.0.0.0 --port 10223 --reload'

echo ""
echo "=== Starting frontend (dev, Vite HMR, port 4203) ==="
echo "    VITE_API_BASE_URL=${BACKEND_API_URL}"
docker run -d \
  --name atm-frontend \
  --restart unless-stopped \
  -p 4203:4203 \
  -v "${BASE_DIR}/frontend:/app" \
  -v atm-frontend-nm:/app/node_modules \
  -e ATM_MODE=dev \
  -e VITE_API_BASE_URL="${BACKEND_API_URL}" \
  atm-frontend:"${VERSION}"

echo ""
echo "======================================"
echo "Dev environment started (image: ${VERSION})"
echo ""
echo "  Frontend : http://${SERVER_IP}:4203"
echo "  Backend  : http://${SERVER_IP}:10223"
echo "  DB Web   : http://${SERVER_IP}:${SQLITE_WEB_PORT}"
echo "  Debugpy  : ${SERVER_IP}:${BACKEND_DEBUG_PORT}"
echo "  API Docs : http://${SERVER_IP}:10223/docs"
echo ""
echo "소스 수정 후 저장하면 자동 반영됩니다."
echo "  Backend  : /opt/atm/backend/app/"
echo "  Frontend : /opt/atm/frontend/src/"
echo ""
echo "로그 확인:"
echo "  docker logs -f atm-backend"
echo "  docker logs -f atm-frontend"
echo "======================================"

docker ps --filter name=atm-
