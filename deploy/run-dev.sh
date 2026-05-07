#!/usr/bin/env bash
set -euo pipefail

# Docker 개발 모드 실행
# - Backend: uvicorn --reload (소스 변경 자동 반영)
# - Frontend: Vite dev server HMR (소스 변경 자동 반영)
# - sqlite-web: backend.dev.env 설정에 따라 선택 실행
#
# Usage: ./deploy/run-dev.sh [IMAGE_VERSION]
# IMAGE_VERSION 생략 시 latest 사용

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ATM_BACKEND_DEV_ENV:-${BASE_DIR}/backend.dev.env}"
BACKEND_DATA_DIR="${BASE_DIR}/backend/data"
VERSION="${1:-latest}"
SERVER_IP="$(hostname -I | awk '{print $1}')"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found."
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
  ' "${ENV_FILE}"
}

env_value() {
  local key="$1"
  local default_value="$2"
  local value="${!key:-}"
  if [[ -z "$value" ]]; then
    value="$(read_env_value "$key")"
  fi
  if [[ -z "$value" ]]; then
    value="$default_value"
  fi
  printf '%s' "$value"
}

BACKEND_PORT="$(env_value BACKEND_PORT 10223)"
FRONTEND_PORT="$(env_value FRONTEND_PORT 4203)"
BACKEND_DEBUG_PORT="$(env_value BACKEND_DEBUG_PORT 5678)"
SQLITE_WEB_ENABLED="$(env_value SQLITE_WEB_ENABLED 1)"
SQLITE_WEB_PORT="$(env_value SQLITE_WEB_PORT 8080)"
SQLITE_WEB_READ_ONLY="$(env_value SQLITE_WEB_READ_ONLY 0)"
VITE_API_BASE_URL="$(env_value VITE_API_BASE_URL "http://${SERVER_IP}:${BACKEND_PORT}")"

mkdir -p "${BACKEND_DATA_DIR}/results/rtd/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/rtd/reports"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/reports"
mkdir -p "${BACKEND_DATA_DIR}/logs"

docker network create atm-net 2>/dev/null || true

BACKEND_PORT_ARGS=(-p "${BACKEND_PORT}:${BACKEND_PORT}")
DEBUG_PORT_ARGS=(-p "${BACKEND_DEBUG_PORT}:${BACKEND_DEBUG_PORT}")
SQLITE_WEB_PORT_ARGS=()
if [[ "${SQLITE_WEB_ENABLED}" == "1" ]]; then
  SQLITE_WEB_PORT_ARGS=(-p "${SQLITE_WEB_PORT}:${SQLITE_WEB_PORT}")
fi

echo "=== Stopping existing containers ==="
docker stop atm-backend atm-frontend 2>/dev/null || true
docker rm   atm-backend atm-frontend 2>/dev/null || true

echo ""
echo "=== Starting backend (dev, --reload) ==="
echo "    env file       : ${ENV_FILE}"
echo "    container user: ${HOST_UID}:${HOST_GID}"
echo "    backend port  : ${BACKEND_PORT}"
echo "    debugpy port  : ${BACKEND_DEBUG_PORT}"
echo "    sqlite-web    : ${SQLITE_WEB_ENABLED}"
echo "    sqlite-web port: ${SQLITE_WEB_PORT}"
echo "    db read-only  : ${SQLITE_WEB_READ_ONLY}"
docker run -d \
  --name atm-backend \
  --network atm-net \
  --restart unless-stopped \
  --user "${HOST_UID}:${HOST_GID}" \
  "${BACKEND_PORT_ARGS[@]}" \
  "${SQLITE_WEB_PORT_ARGS[@]}" \
  "${DEBUG_PORT_ARGS[@]}" \
  -v "${BASE_DIR}/backend/app:/app/app" \
  -v "${BACKEND_DATA_DIR}:/data" \
  -e BACKEND_PORT="${BACKEND_PORT}" \
  -e BACKEND_DEBUG_PORT="${BACKEND_DEBUG_PORT}" \
  -e SQLITE_WEB_ENABLED="${SQLITE_WEB_ENABLED}" \
  -e SQLITE_WEB_PORT="${SQLITE_WEB_PORT}" \
  -e SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY}" \
  --env-file "${ENV_FILE}" \
  atm-backend:"${VERSION}" \
  sh -c 'if [ "${SQLITE_WEB_ENABLED:-1}" = "1" ]; then touch "${DB_PATH:-/data/autotestmanager.db}"; readonly_arg=""; if [ "${SQLITE_WEB_READ_ONLY:-0}" = "1" ]; then readonly_arg="--read-only"; fi; sqlite_web --host=0.0.0.0 --port="${SQLITE_WEB_PORT:-8080}" --no-browser ${readonly_arg} "${DB_PATH:-/data/autotestmanager.db}" & fi; exec python -m debugpy --listen "0.0.0.0:${BACKEND_DEBUG_PORT:-5678}" -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-10223}" --reload'

echo ""
echo "=== Starting frontend (dev, Vite HMR) ==="
echo "    frontend port : ${FRONTEND_PORT}"
echo "    VITE_API_BASE_URL=${VITE_API_BASE_URL}"
docker run -d \
  --name atm-frontend \
  --restart unless-stopped \
  -p "${FRONTEND_PORT}:4203" \
  -v "${BASE_DIR}/frontend:/app" \
  -v atm-frontend-nm:/app/node_modules \
  -e ATM_MODE=dev \
  -e VITE_API_BASE_URL="${VITE_API_BASE_URL}" \
  atm-frontend:"${VERSION}"

echo ""
echo "======================================"
echo "Dev environment started (image: ${VERSION})"
echo ""
echo "  Frontend : http://${SERVER_IP}:${FRONTEND_PORT}"
echo "  Backend  : http://${SERVER_IP}:${BACKEND_PORT}"
if [[ "${SQLITE_WEB_ENABLED}" == "1" ]]; then
echo "  DB Web   : http://${SERVER_IP}:${SQLITE_WEB_PORT}"
fi
echo "  Debugpy  : ${SERVER_IP}:${BACKEND_DEBUG_PORT}"
echo "  API Docs : http://${SERVER_IP}:${BACKEND_PORT}/docs"
echo ""
echo "소스 수정 후 저장하면 자동 반영됩니다."
echo "  Backend  : ${BASE_DIR}/backend/app/"
echo "  Frontend : ${BASE_DIR}/frontend/src/"
echo ""
echo "로그 확인:"
echo "  docker logs -f atm-backend"
echo "  docker logs -f atm-frontend"
echo "======================================"

docker ps --filter name=atm-
