#!/usr/bin/env bash
set -euo pipefail

# atm 공통 컨테이너 종료/삭제
# - 개발/운영 모드 모두 동일한 컨테이너 이름 사용
#
# Usage: ./deploy/stop.sh

CONTAINERS=(atm-backend atm-frontend)

echo "=== Stopping ATM containers ==="
docker stop "${CONTAINERS[@]}" 2>/dev/null || true

echo ""
echo "=== Removing ATM containers ==="
docker rm "${CONTAINERS[@]}" 2>/dev/null || true

echo ""
echo "=== Remaining ATM containers ==="
docker ps -a --filter name=atm-
