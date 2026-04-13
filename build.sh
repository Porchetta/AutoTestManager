#!/usr/bin/env bash
set -euo pipefail

# AutoTestManager 이미지 빌드 + 배포 패키지 생성
# 사외(인터넷 가능) 환경에서 실행
#
# Usage: ./build.sh
#
# 결과물:
#   atm-images-YYYYMMDD_HHMM.tar.gz  - Docker 이미지 (backend + frontend)
#   atm-source-YYYYMMDD_HHMM.tar.gz  - 소스코드 + deploy 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(date +%Y%m%d_%H%M)
IMAGE_TAR="${SCRIPT_DIR}/atm-images-${VERSION}.tar.gz"
SOURCE_TAR="${SCRIPT_DIR}/atm-source-${VERSION}.tar.gz"

cd "${SCRIPT_DIR}"

echo "=== [1/3] Building backend image (atm-backend:${VERSION}) ==="
docker build -t atm-backend:"${VERSION}" -t atm-backend:latest ./backend

echo ""
echo "=== [2/3] Building frontend image (atm-frontend:${VERSION}) ==="
docker build -t atm-frontend:"${VERSION}" -t atm-frontend:latest ./frontend

echo ""
echo "=== [3/3] Packaging ==="

echo "  -> Saving Docker images to ${IMAGE_TAR}"
docker save atm-backend:"${VERSION}" atm-frontend:"${VERSION}" | gzip > "${IMAGE_TAR}"

echo "  -> Packaging source to ${SOURCE_TAR}"
tar czf "${SOURCE_TAR}" \
  --exclude='backend/.venv' \
  --exclude='backend/__pycache__' \
  --exclude='backend/data' \
  --exclude='backend/.env' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='frontend/.env' \
  backend/app \
  backend/.env.example \
  frontend/src \
  frontend/public \
  frontend/index.html \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/vite.config.js \
  frontend/.env.example \
  deploy/ 2>/dev/null || \
tar czf "${SOURCE_TAR}" \
  --exclude='backend/.venv' \
  --exclude='backend/__pycache__' \
  --exclude='backend/data' \
  --exclude='backend/.env' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='frontend/.env' \
  backend/app \
  backend/.env.example \
  frontend/src \
  frontend/public \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/vite.config.js \
  frontend/.env.example \
  deploy/

echo ""
echo "======================================"
echo "Build complete: version=${VERSION}"
echo ""
echo "Transfer these files to the production server:"
echo "  ${IMAGE_TAR}"
echo "  ${SOURCE_TAR}"
echo ""
echo "Then on the production server:"
echo "  chmod +x deploy/setup.sh deploy/run-dev.sh deploy/run-prod.sh"
echo "  ./deploy/setup.sh ${IMAGE_TAR##*/} ${SOURCE_TAR##*/}"
echo "======================================"
