# MSS 테스트 매니저

RTD 및 ezDFS 테스트 스크립트 실행을 자동화하는 웹 기반 플랫폼입니다.

## 🏗 아키텍처

- **프런트엔드**: Vue 3 + Vite + Pinia (포트: 40203)
- **백엔드**: FastAPI + SQLAlchemy (포트: 40223)
- **데이터베이스**: MySQL 8.0 (포트: 3306)
- **인프라**: Docker Compose

## 🚀 시작하기

### 사전 준비
- Docker 및 Docker Compose 설치

### 설치 및 실행

1. **저장소를 클론**합니다(이미 클론했다면 건너뜁니다).
2. **서비스를 시작**합니다:
   ```bash
   docker-compose up --build -d
   ```
3. **애플리케이션에 접속**합니다:
   - 프런트엔드: [http://localhost:40203](http://localhost:40203)
   - 백엔드 API 문서: [http://localhost:40223/docs](http://localhost:40223/docs)

### 사전 빌드 이미지를 사용한 오프라인 실행
인터넷이 없는 환경에 배포해야 한다면, 인터넷이 되는 장비에서 이미지를 빌드·저장한 뒤 오프라인 환경에서 로드하여 실행하세요.

1. **온라인에서 이미지 빌드 및 태그 지정**:
   ```bash
   docker compose build
   docker tag autotestmanager-frontend:latest mss-frontend:offline
   docker tag autotestmanager-backend:latest mss-backend:offline
   # mysql:8.0은 자동으로 pull되므로, 오프라인 호스트에 이미지가 없다면 함께 저장하세요
   ```
2. **이미지를 휴대용 tar 파일로 저장**(`./images` 아래에 보관 권장):
   ```bash
   mkdir -p images
   docker save mss-frontend:offline -o images/frontend.tar
   docker save mss-backend:offline -o images/backend.tar
   docker save mysql:8.0 -o images/db.tar
   ```
3. **저장소와 tar 파일을 오프라인 호스트로 전송**합니다.
4. **오프라인 헬퍼 스크립트 실행**(이미지를 로드하고 빌드 없이 컨테이너를 시작):
   ```bash
   ./offline-run.sh
   ```
   - 필요하면 tar 경로나 태그를 덮어쓸 수 있습니다:
     ```bash
     FRONTEND_TAR=/path/frontend.tar BACKEND_TAR=/path/backend.tar DB_TAR=/path/db.tar \
     FRONTEND_IMAGE=my-frontend:prod BACKEND_IMAGE=my-backend:prod DB_IMAGE=mysql:8.0 \
     ./offline-run.sh
     ```

### 오프라인 빌드(빌드 호스트도 인터넷이 없을 때)
빌드 환경에도 네트워크가 없다면, 온라인에서 의존성을 미리 수집해 `./offline` 폴더를 복사한 뒤 네트워크 없이 빌드하세요.

1. **온라인에서 미리 준비**(Python wheel과 npm 캐시가 `./offline` 아래에 채워집니다):
   ```bash
   ./offline-prep.sh
   ```
2. **오프라인 호스트로 복사**: 저장소와 생성된 `./offline` 디렉터리를 전송합니다.
3. **캐시된 의존성으로 오프라인 빌드**(오프라인 환경에 python+pip, node+npm, docker가 설치되어 있어야 합니다):
   ```bash
   ./offline-build.sh
   ```
   - 백엔드 의존성은 `offline/pip-wheels`에서 `pip install --no-index`로 설치됩니다.
   - 프런트엔드 의존성은 `offline/npm-cache`에서 `npm ci --offline`으로 설치됩니다.
   - 두 이미지 모두 `--network=none`으로 빌드해 인터넷 사용을 차단합니다.
4. **실행**: 이미지를 저장했다면 `./offline-run.sh`, 또는 오프라인에서 빌드한 이미지를 이용해 `docker compose up -d`를 실행합니다.
   - 오프라인 컴포즈 파일(`docker-compose.offline.yml`)은 사전 빌드된 이미지만 사용하며, 소스 코드를 바인드 마운트하지 않습니다. 백엔드나 프런트엔드 소스를 변경했다면 새로 빌드·태그한 이미지를 사용하세요.

### 초기 로그인 정보
- **아이디**: `admin`
- **비밀번호**: `admin123` (첫 로그인 후 "마이 페이지" 또는 관리자 도구에서 반드시 변경하세요)

## 📂 프로젝트 구조

```
/AutoTestManager
├── backend/            # FastAPI 애플리케이션
│   ├── app/
│   │   ├── routers/    # API 엔드포인트 (Auth, Admin, RTD, ezDFS)
│   │   ├── models.py   # DB 모델
│   │   └── ...
│   └── Dockerfile
├── frontend/           # Vue 3 애플리케이션
│   ├── src/
│   │   ├── views/      # 페이지 컴포넌트
│   │   ├── stores/     # Pinia 상태 관리
│   │   └── ...
│   └── Dockerfile
├── database/           # 데이터베이스 스크립트
│   └── init.sql
└── docker-compose.yml
```

## 🧪 주요 기능

- **RTD 테스트**: 특정 라인에 대한 RTD 테스트를 단계별로 실행할 수 있는 마법사.
- **ezDFS 테스트**: 서버와 룰을 선택해 테스트를 실행하고 즐겨찾기를 지원.
- **관리자 기능**: 사용자 승인/승격 및 시스템 설정 관리.
- **마이 페이지**: 이력 조회 및 비밀번호 변경.
