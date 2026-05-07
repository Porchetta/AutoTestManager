#!/usr/bin/env bash
set -euo pipefail

# AutoTestManager 서버 최초 초기화 스크립트
# 1회만 실행. 이미지 로드 + 데이터 디렉토리 생성 + env 파일 생성
#
# Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz>

IMAGE_TAR="${1:?Usage: ./deploy/setup.sh <atm-images-xxx.tar.gz>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DATA_DIR="${BASE_DIR}/backend/data"
DEV_ENV="${BASE_DIR}/backend.dev.env"
PROD_ENV="${BASE_DIR}/backend.prod.env"
DEV_ENV_EXAMPLE="${BASE_DIR}/deploy/env/backend.dev.env.example"
PROD_ENV_EXAMPLE="${BASE_DIR}/deploy/env/backend.prod.env.example"
LEGACY_ENV="${BASE_DIR}/backend.env"

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

echo "=== [4/4] Creating environment files ==="
if [[ ! -f "${DEV_ENV}" ]]; then
  cp "${DEV_ENV_EXAMPLE}" "${DEV_ENV}"
  echo "  created: ${DEV_ENV}"
else
  echo "  exists : ${DEV_ENV}"
fi

if [[ ! -f "${PROD_ENV}" ]]; then
  cp "${PROD_ENV_EXAMPLE}" "${PROD_ENV}"
  echo "  created: ${PROD_ENV}"
else
  echo "  exists : ${PROD_ENV}"
fi

echo ""
echo "======================================"
echo "Setup complete."
echo ""
echo "반드시 아래 파일을 환경에 맞게 편집하세요:"
echo "  개발 모드: ${DEV_ENV}"
echo "  운영 모드: ${PROD_ENV}"
echo ""
echo "변경 필수 항목:"
echo "  - JWT_SECRET_KEY"
echo "  - DEFAULT_ADMIN_PASSWORD"
echo "  - SVN_UPLOAD_*"
echo ""
if [[ -f "${LEGACY_ENV}" ]]; then
  echo "Legacy env detected:"
  echo "  ${LEGACY_ENV}"
  echo "필요한 값을 backend.dev.env/backend.prod.env로 옮긴 뒤 삭제하세요."
  echo ""
fi
echo "실행:"
echo "  개발 모드: ./deploy/run-dev.sh"
echo "  운영 모드: ./deploy/run-prod.sh"
echo "======================================"
