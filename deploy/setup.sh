#!/usr/bin/env bash
set -euo pipefail

# AutoTestManager 운영 서버 최초 초기화 스크립트
# 1회만 실행. 이미지 로드 + 데이터 디렉토리 생성 + env 파일 생성
#
# Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz>

IMAGE_TAR="${1:?Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz>}"
BASE_DIR="/home/hyun/develope/AutoTestManager"
BACKEND_DATA_DIR="${BASE_DIR}/backend/data"

echo "=== [1/4] Creating data directory structure ==="
mkdir -p "${BACKEND_DATA_DIR}/results/rtd/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/rtd/reports"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/raw"
mkdir -p "${BACKEND_DATA_DIR}/results/ezdfs/reports"
mkdir -p "${BACKEND_DATA_DIR}/logs"

echo "=== [2/4] Loading Docker images (${IMAGE_TAR}) ==="
docker load < "${IMAGE_TAR}"

echo "=== [3/4] Creating Docker network ==="
docker network create atm-net 2>/dev/null || echo "  (atm-net already exists, skipping)"

echo "=== [4/4] Creating backend.env ==="
if [[ ! -f "${BASE_DIR}/backend.env" ]]; then
  cp "${BASE_DIR}/deploy/backend.env.example" "${BASE_DIR}/backend.env"
  echo ""
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
  echo "  (backend.env already exists, skipping)"
  echo ""
  echo "======================================"
  echo "Setup complete."
  echo ""
  echo "실행:"
  echo "   개발 모드: ./deploy/run-dev.sh"
  echo "   운영 모드: ./deploy/run-prod.sh"
  echo "======================================"
fi
