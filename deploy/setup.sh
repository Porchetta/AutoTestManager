#!/usr/bin/env bash
set -euo pipefail

# AutoTestManager 운영 서버 최초 초기화 스크립트
# 1회만 실행. 이미지 로드 + 디렉토리 구성 + env 파일 생성
#
# Usage: ./deploy/setup.sh <images.tar.gz> <source.tar.gz>

IMAGE_TAR="${1:?Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz> <atm-source-xxx.tar.gz>}"
SOURCE_TAR="${2:?Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz> <atm-source-xxx.tar.gz>}"
BASE_DIR="/opt/atm"

echo "=== [1/4] Creating directory structure under ${BASE_DIR} ==="
mkdir -p "${BASE_DIR}/backend/app"
mkdir -p "${BASE_DIR}/frontend/src"
mkdir -p "${BASE_DIR}/data/results/rtd/raw"
mkdir -p "${BASE_DIR}/data/results/rtd/reports"
mkdir -p "${BASE_DIR}/data/results/ezdfs/raw"
mkdir -p "${BASE_DIR}/data/results/ezdfs/reports"
mkdir -p "${BASE_DIR}/data/logs"

echo "=== [2/4] Extracting source (${SOURCE_TAR}) ==="
tar xzf "${SOURCE_TAR}" -C "${BASE_DIR}"

echo "=== [3/4] Loading Docker images (${IMAGE_TAR}) ==="
docker load < "${IMAGE_TAR}"

echo "=== [4/4] Creating Docker network ==="
docker network create atm-net 2>/dev/null || echo "  (atm-net already exists, skipping)"

echo ""
if [[ ! -f "${BASE_DIR}/backend.env" ]]; then
  cp "${BASE_DIR}/deploy/backend.env.example" "${BASE_DIR}/backend.env"
  echo "======================================"
  echo "Setup complete."
  echo ""
  echo "⚠  반드시 아래 파일을 편집하세요:"
  echo "   ${BASE_DIR}/backend.env"
  echo ""
  echo "   변경 필수 항목:"
  echo "   - JWT_SECRET_KEY  (임의의 긴 문자열로 변경)"
  echo "   - DEFAULT_ADMIN_PASSWORD  (최초 관리자 비밀번호)"
  echo ""
  echo "편집 후 실행:"
  echo "   개발 모드: ./deploy/run-dev.sh"
  echo "   운영 모드: ./deploy/run-prod.sh"
  echo "======================================"
else
  echo "======================================"
  echo "Setup complete. (backend.env already exists, skipped)"
  echo ""
  echo "실행:"
  echo "   개발 모드: ./deploy/run-dev.sh"
  echo "   운영 모드: ./deploy/run-prod.sh"
  echo "======================================"
fi
