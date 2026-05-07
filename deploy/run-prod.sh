#!/usr/bin/env bash
set -euo pipefail

# Docker 운영 모드 실행
# - Backend: uvicorn (reload 없음)
# - Frontend: npm run build → nginx 서빙 (포트 4203)
# - nginx가 /api/* 요청을 atm-backend:${BACKEND_PORT}로 프록시
# - Backend 포트는 외부 미노출 (atm-net 내부 통신)
# - sqlite-web: backend.prod.env 설정에 따라 선택 실행
#
# Usage: ./deploy/run-prod.sh [IMAGE_VERSION]
# IMAGE_VERSION 생략 시 latest 사용

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ATM_BACKEND_PROD_ENV:-${BASE_DIR}/backend.prod.env}"
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
SQLITE_WEB_ENABLED="$(env_value SQLITE_WEB_ENABLED 0)"
SQLITE_WEB_PORT="$(env_value SQLITE_WEB_PORT 8080)"
SQLITE_WEB_READ_ONLY="$(env_value SQLITE_WEB_READ_ONLY 1)"
VITE_API_BASE_URL="$(env_value VITE_API_BASE_URL "http://${SERVER_IP}:${FRONTEND_PORT}")"

mkdir -p "${BACKEND_DATA_DIR}/results/rtd/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/rtd/reports"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/reports"
mkdir -p "${BACKEND_DATA_DIR}/logs"

docker network create atm-net 2>/dev/null || true

SQLITE_WEB_PORT_ARGS=()
if [[ "${SQLITE_WEB_ENABLED}" == "1" ]]; then
  SQLITE_WEB_PORT_ARGS=(-p "${SQLITE_WEB_PORT}:${SQLITE_WEB_PORT}")
fi

echo "=== Stopping existing containers ==="
docker stop atm-backend atm-frontend 2>/dev/null || true
docker rm   atm-backend atm-frontend 2>/dev/null || true

echo ""
echo "=== Starting backend (prod) ==="
echo "    env file       : ${ENV_FILE}"
echo "    container user: ${HOST_UID}:${HOST_GID}"
echo "    backend port  : ${BACKEND_PORT} (internal)"
echo "    sqlite-web    : ${SQLITE_WEB_ENABLED}"
echo "    sqlite-web port: ${SQLITE_WEB_PORT}"
echo "    db read-only  : ${SQLITE_WEB_READ_ONLY}"
docker run -d \
  --name atm-backend \
  --network atm-net \
  --restart unless-stopped \
  --user "${HOST_UID}:${HOST_GID}" \
  "${SQLITE_WEB_PORT_ARGS[@]}" \
  -v "${BASE_DIR}/backend/app:/app/app" \
  -v "${BACKEND_DATA_DIR}:/data" \
  -e BACKEND_PORT="${BACKEND_PORT}" \
  -e SQLITE_WEB_ENABLED="${SQLITE_WEB_ENABLED}" \
  -e SQLITE_WEB_PORT="${SQLITE_WEB_PORT}" \
  -e SQLITE_WEB_READ_ONLY="${SQLITE_WEB_READ_ONLY}" \
  --env-file "${ENV_FILE}" \
  atm-backend:"${VERSION}" \
  sh -c 'if [ "${SQLITE_WEB_ENABLED:-0}" = "1" ]; then touch "${DB_PATH:-/data/autotestmanager.db}"; readonly_arg=""; if [ "${SQLITE_WEB_READ_ONLY:-1}" = "1" ]; then readonly_arg="--read-only"; fi; sqlite_web --host=0.0.0.0 --port="${SQLITE_WEB_PORT:-8080}" --no-browser ${readonly_arg} "${DB_PATH:-/data/autotestmanager.db}" & fi; exec uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-10223}"'

echo ""
echo "=== Starting frontend (prod, building dist then nginx) ==="
echo "    frontend port : ${FRONTEND_PORT}"
echo "    VITE_API_BASE_URL=${VITE_API_BASE_URL}"
echo "    (빌드 시작... 수 분 소요될 수 있습니다)"
docker run -d \
  --name atm-frontend \
  --network atm-net \
  --restart unless-stopped \
  -p "${FRONTEND_PORT}:4203" \
  -v "${BASE_DIR}/frontend:/app" \
  -v atm-frontend-nm:/app/node_modules \
  -e ATM_MODE=prod \
  -e BACKEND_PORT="${BACKEND_PORT}" \
  -e VITE_API_BASE_URL="${VITE_API_BASE_URL}" \
  atm-frontend:"${VERSION}"

echo ""
echo "======================================"
echo "Production environment started (image: ${VERSION})"
echo ""
echo "  Service  : http://${SERVER_IP}:${FRONTEND_PORT}"
if [[ "${SQLITE_WEB_ENABLED}" == "1" ]]; then
echo "  DB Web   : http://${SERVER_IP}:${SQLITE_WEB_PORT}"
fi
echo "  (backend port ${BACKEND_PORT} 외부 미노출 - nginx 프록시 사용)"
echo ""
echo "frontend 빌드 완료 확인:"
echo "  docker logs -f atm-frontend"
echo ""
echo "건강 상태 확인:"
echo "  curl http://${SERVER_IP}:${FRONTEND_PORT}/health"
echo "======================================"

docker ps --filter name=atm-
