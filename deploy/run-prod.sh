#!/usr/bin/env bash
set -euo pipefail

# 운영 모드 실행
# - Backend: uvicorn (reload 없음)
# - Frontend: npm run build → nginx 서빙 (포트 20216)
# - nginx가 /api/* 요청을 atm-backend:8000으로 프록시
# - Backend 포트는 외부 미노출 (atm-net 내부 통신)
#
# Usage: ./deploy/run-prod.sh [IMAGE_VERSION]
# IMAGE_VERSION 생략 시 latest 사용

BASE_DIR="/opt/atm"
VERSION="${1:-latest}"
SERVER_IP="$(hostname -I | awk '{print $1}')"
SERVER_URL="http://${SERVER_IP}:20216"

if [[ ! -f "${BASE_DIR}/backend.env" ]]; then
  echo "ERROR: ${BASE_DIR}/backend.env not found."
  echo "Run ./deploy/setup.sh first."
  exit 1
fi

echo "=== Stopping existing containers ==="
docker stop atm-backend atm-frontend 2>/dev/null || true
docker rm   atm-backend atm-frontend 2>/dev/null || true

echo ""
echo "=== Starting backend (prod) ==="
docker run -d \
  --name atm-backend \
  --network atm-net \
  --restart unless-stopped \
  -v "${BASE_DIR}/backend/app:/app/app" \
  -v "${BASE_DIR}/data:/data" \
  --env-file "${BASE_DIR}/backend.env" \
  atm-backend:"${VERSION}"

echo ""
echo "=== Starting frontend (prod, building dist then nginx:20216) ==="
echo "    VITE_API_BASE_URL=${SERVER_URL}"
echo "    (빌드 시작... 수 분 소요될 수 있습니다)"
docker run -d \
  --name atm-frontend \
  --network atm-net \
  --restart unless-stopped \
  -p 20216:20216 \
  -v "${BASE_DIR}/frontend:/app" \
  -v atm-frontend-nm:/app/node_modules \
  -e ATM_MODE=prod \
  -e VITE_API_BASE_URL="${SERVER_URL}" \
  atm-frontend:"${VERSION}"

echo ""
echo "======================================"
echo "Production environment started (image: ${VERSION})"
echo ""
echo "  Service  : http://${SERVER_IP}:20216"
echo "  (backend port 20223 외부 미노출 - nginx 프록시 사용)"
echo ""
echo "frontend 빌드 완료 확인:"
echo "  docker logs -f atm-frontend"
echo ""
echo "건강 상태 확인:"
echo "  curl http://${SERVER_IP}:20216/health"
echo "======================================"

docker ps --filter name=atm-
