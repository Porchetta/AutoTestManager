# AutoTestManager 배포 가이드

## 구조 개요

```
[사외 개발 환경]          [사내 서버 - RHEL 7.9, 오프라인]
 WSL / 인터넷 가능    →     docker run 만 사용 가능
                            git repo로 소스 관리
```

- **Docker 이미지**: 사외에서 빌드 → tar.gz로 반입
- **소스 코드**: git repo로 사내 반입 (이미지에 미포함, 컨테이너에 볼륨 마운트)
- **데이터 (DB, 결과 파일)**: 사내 서버 `/opt/atm/data/` 에 영구 보존

---

## 사전 준비

### 사외 개발 환경
- Docker 설치
- git 설치
- Node.js 20+ 설치 (빌드 스크립트 내부에서 Docker로 대체 가능하므로 필수 아님)

### 사내 서버 (RHEL 7.9)
- Docker CE 설치 확인
  ```bash
  docker --version
  ```
- 방화벽 포트 개방
  ```bash
  # 개발 모드
  firewall-cmd --permanent --add-port=10223/tcp   # Backend API
  firewall-cmd --permanent --add-port=4203/tcp   # Frontend Vite

  # 운영 모드 (4203만 필요, backend는 내부 통신)
  firewall-cmd --permanent --add-port=4203/tcp

  firewall-cmd --reload
  ```

---

## STEP 1 — 사외: Docker 이미지 빌드

소스를 수정한 뒤, 사외 개발 환경(WSL)에서 이미지를 빌드합니다.

```bash
# 프로젝트 루트에서 실행
./build.sh
```

생성 결과:
```
atm-images-YYYYMMDD_HHMM.tar.gz   ← 사내로 반입할 파일
```

> **이미지 재빌드가 필요한 경우**
> - `backend/requirements.txt` 변경 시
> - `frontend/package.json` 변경 시
> - Dockerfile 변경 시
>
> **이미지 재빌드가 불필요한 경우**
> - `backend/app/` Python 소스 변경 → git pull 후 자동 반영
> - `frontend/src/` Vue 소스 변경 → git pull 후 자동 반영

---

## STEP 2 — 사내로 반입

| 항목 | 방법 |
|---|---|
| Docker 이미지 | USB 등으로 `atm-images-YYYYMMDD_HHMM.tar.gz` 복사 |
| 소스 코드 | git repo를 사내 git 서버에 push하거나, `.git` 포함 디렉토리째 복사 |

---

## STEP 3 — 사내: 최초 초기화 (1회만)

### 3-1. 소스 clone

```bash
# 사내 git 서버가 있는 경우
git clone http://내부git서버/AutoTestManager /opt/atm

# git 디렉토리를 직접 복사한 경우
cp -r /media/usb/AutoTestManager /opt/atm
```

### 3-2. setup.sh 실행 (이미지 로드 + 디렉토리 생성 + env 파일 생성)

```bash
cd /opt/atm
chmod +x deploy/setup.sh
./deploy/setup.sh atm-images-YYYYMMDD_HHMM.tar.gz
```

확인:
```bash
docker images | grep atm
# atm-backend   20260414_1030   ...
# atm-frontend  20260414_1030   ...
```

### 3-3. 환경 변수 설정

```bash
vi /opt/atm/backend.env
```

반드시 변경할 항목:
```env
JWT_SECRET_KEY=임의의-긴-랜덤-문자열-여기에-입력   # 필수
DEFAULT_ADMIN_PASSWORD=변경할-관리자-비밀번호       # 필수
```

> `DEFAULT_ADMIN_PASSWORD`는 **최초 컨테이너 실행 시** DB에 seed됩니다.
> 이후에는 웹 UI → My Page에서 변경하세요.

---

## STEP 4 — 실행

### 개발 모드

소스를 수정하면서 테스트할 때 사용합니다.

```bash
cd /opt/atm
chmod +x deploy/run-dev.sh
./deploy/run-dev.sh
```

| 접속 | URL |
|---|---|
| Frontend (Vite HMR) | `http://서버IP:4203` |
| Backend API | `http://서버IP:10223` |
| Swagger Docs | `http://서버IP:10223/docs` |

**소스 수정 반영 방식:**

```
backend/app/*.py 수정 → 저장 → uvicorn --reload 자동 재시작 (수 초)
frontend/src/*.vue 수정 → 저장 → Vite HMR 브라우저 즉시 반영
컨테이너 재시작 불필요
```

---

### 운영 모드

사용자에게 서비스를 제공할 때 사용합니다.

```bash
cd /opt/atm
chmod +x deploy/run-prod.sh
./deploy/run-prod.sh
```

| 접속 | URL |
|---|---|
| 서비스 전체 | `http://서버IP:4203` |

- Frontend: nginx가 정적 파일 서빙 (빌드 포함, 수 분 소요)
- Backend: 외부 미노출, nginx가 `/api/*` → `atm-backend:10223` 프록시

---

## STEP 5 — 업데이트

### 소스 코드만 변경된 경우 (의존성 변경 없음)

```bash
# 사내 서버에서
cd /opt/atm
git pull

# 개발 모드: uvicorn --reload가 자동 감지 → 재시작 불필요
# 운영 모드: 컨테이너 재시작으로 반영
docker restart atm-backend
docker restart atm-frontend   # prod 모드는 재시작 시 npm run build 재실행
```

### 의존성이 변경된 경우 (requirements.txt / package.json)

```bash
# [사외] 이미지 재빌드
./build.sh

# [사외 → 사내] 새 tar.gz 반입
# [사내] 이미지 재로드
docker load < atm-images-NEW.tar.gz

# node_modules 볼륨 초기화 (프론트엔드 패키지 변경 시)
docker volume rm atm-frontend-nm

# 컨테이너 재시작
./deploy/run-dev.sh    # 또는 run-prod.sh
```

---

## 유용한 명령어

```bash
# 컨테이너 상태 확인
docker ps --filter name=atm-

# 로그 확인
docker logs -f atm-backend
docker logs -f atm-frontend

# 헬스 체크
curl http://서버IP:4203/health    # 운영 모드
curl http://서버IP:10223/health    # 개발 모드

# 컨테이너 중지
docker stop atm-backend atm-frontend

# 데이터 보존 확인 (컨테이너 삭제 후에도 유지)
ls /opt/atm/data/
```

---

## 디렉토리 구조 (사내 서버)

```
/opt/atm/
├── backend/
│   └── app/              ← 컨테이너 마운트 (소스)
├── frontend/
│   └── src/              ← 컨테이너 마운트 (소스)
├── data/                 ← 컨테이너 마운트 (영구 보존)
│   ├── autotestmanager.db
│   ├── results/
│   └── logs/
├── backend.env           ← 환경 변수 (git 미포함, 서버에서 직접 관리)
└── deploy/
    ├── run-dev.sh
    ├── run-prod.sh
    └── backend.env.example
```
