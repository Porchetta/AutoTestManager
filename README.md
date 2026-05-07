# AutoTestManager

MSS 개발자가 **RTD (Rule Test Dispatcher)** / **ezDFS** rule 시스템에 대한
테스트 실행과 결과 관리를 웹에서 수행할 수 있도록 만든 사내 도구입니다.
Vue 3 SPA 와 FastAPI 백엔드로 구성되며, **폐쇄망(오프라인)** 환경에서
Docker image 로 배포됩니다.

---

## 무엇을 하는가

- 사업부 → 개발 라인 → Rule → 버전을 **단계형 위저드**로 선택
- 선택한 Rule 을 대상 서버에 **복사 → 컴파일 → 테스트**하는 원격 실행 제어
- 여러 타겟 라인에 대한 테스트를 동시에 실행하고 **모니터링**
- Raw 출력과 `.xlsx` 요약 결과서 **다운로드**
- 테스트 통과 후 **SVN 체크인** (`svn_upload_custom.py` 훅)
- 사용자별 / 테스트 종류별 **위저드 세션 자동 복원**
- 관리자용 **User / Host / RTD / ezDFS Config** CRUD 콘솔

---

## 아키텍처 한눈에 보기

```
            브라우저                 FastAPI 백엔드               원격 호스트
  ┌───────────────────┐       ┌────────────────────┐       ┌───────────────┐
  │  Vue 3 SPA        │  REST │  FastAPI / Pydantic│  SSH  │ RTD / ezDFS   │
  │  Pinia + Vite     │◀─────▶│  SQLAlchemy 2.0    │◀─────▶│ 테스트 서버   │
  │  Composition API  │  JSON │  SQLite + Paramiko │       │ (rule compile │
  │  (port 4203)      │       │  (port 10223)      │       │  / test run)  │
  └───────────────────┘       └────────────────────┘       └───────────────┘
                                        │
                                        ▼
                                 ┌─────────────┐
                                 │ data/       │
                                 │  autotestmanager.db
                                 │  results/   │
                                 │  logs/      │
                                 └─────────────┘
```

- **Frontend**: Vue 3 + Pinia + Vue Router + Axios. CSS 는 자체 토큰 기반
  디자인 시스템 (`src/styles/`)
- **Backend**: FastAPI + SQLAlchemy 2.0 + SQLite + python-jose (JWT)
  + Paramiko (SSH) + openpyxl (xlsx)
- **배포**: 온라인 환경에서 Docker image 를 build → tar.gz 로 이관 →
  운영 서버에서 `docker run` + **소스 mount** 방식. 운영 서버는 RHEL 7.9

---

## 주요 기능

### 인증 / 권한
- 회원가입 → 관리자 승인 → 로그인
- JWT 기반 세션, 관리자 전용 API 가드
- 비밀번호 변경 (My Page)

### RTD Test Manager (6 단계)
1. 사업부 선택
2. 개발 라인 선택
3. Rule / Version 선택 (SSH 로 dev 라인 조회)
4. Macro 탐색 — `탐색` 클릭 시에만 old/new `.report` 파싱 후 diff
5. 타겟 라인 선택 (`{line_name}_TARGET` 접미사 구분)
6. 실행 제어: `복사`, `컴파일`, `테스트`, `테스트 결과서 생성`, `Execute all`
   - Target Status Monitor 에서 라인별 상태와 Raw Data 다운로드
   - 모든 과정 통과 시 SVN Upload 가능

### ezDFS Test (4 단계)
1. Module 선택
2. Rule 선택
3. Sub Rule 확인
4. 실행 / 결과서 다운로드 / SVN Upload

### Admin Console
- **User Management** — 사용자 승인, 모듈 지정, 관리자 권한 토글, 삭제
- **Host Settings** — Host 등록, credential 다중 관리, SSH 병렬 제한 감지
- **RTD Settings** — 사업부별 line config CRUD
- **ezDFS Settings** — module config CRUD

### My Page
- 비밀번호 변경
- RTD / ezDFS 최근 테스트 결과 조회 + 다운로드

---

## 빠른 시작 (Docker 개발 모드)

개발 환경은 **Windows + WSL2 (Ubuntu)** 기준입니다.

```bash
./build.sh
./deploy/setup.sh atm-images-YYYYMMDD_HHMM.tar.gz
vi backend.dev.env
./deploy/run-dev.sh
```

| 경로 | URL |
|---|---|
| Frontend | `http://127.0.0.1:4203` |
| API | `http://127.0.0.1:10223` |
| Swagger | `http://127.0.0.1:10223/docs` |
| Health | `http://127.0.0.1:10223/health` |
| DB Web | `http://127.0.0.1:8080` |

기본 관리자 계정: `admin` / `admin1234`
(최초 기동 시 `bootstrap.seed_admin()` 이 자동 생성)

실제 환경값은 git에 포함하지 않는 `backend.dev.env`, `backend.prod.env`에서 관리합니다.
예제 파일은 `deploy/env/` 아래에 있습니다.

---

## 환경 파일 구조

기존의 단일 `backend.env` 를 **dev / prod 두 개의 env 파일**로 분리했습니다.
실제 값은 git에 포함하지 않으며, 템플릿만 `deploy/env/` 아래에 둡니다.

```
AutoTestManager/
├── backend.dev.env              ← 개발 모드 실값 (gitignored)
├── backend.prod.env             ← 운영 모드 실값 (gitignored)
└── deploy/
    ├── run-dev.sh               ← 공식 개발 실행 진입점
    ├── run-prod.sh              ← 공식 운영 실행 진입점
    ├── setup.sh                 ← 이미지 load + env 템플릿 복사
    └── env/
        ├── backend.dev.env.example
        └── backend.prod.env.example
```

- 로컬 전용 `backend/dev-setup.sh`, `backend/run-dev.sh` 와 단일 `backend.env`/
  `frontend/.env` 는 제거되었습니다. 모든 실행은 `deploy/run-dev.sh` /
  `deploy/run-prod.sh` 로 일원화됩니다.
- `.gitignore` 가 `backend*.env`, `backend/.env`, `frontend/.env`,
  `deploy/env/*.env` 를 모두 추적 제외합니다.
- 운영 서버에서는 `deploy/setup.sh` 가 처음 실행될 때 `deploy/env/*.example`
  을 루트의 `backend.dev.env` / `backend.prod.env` 로 복사합니다.

---

## DB Web (sqlite-web)

개발 중 SQLite DB(`backend/data/autotestmanager.db`)를 브라우저에서 바로
조회/편집할 수 있도록 **sqlite-web** 을 backend 컨테이너에 함께 띄웁니다.

| 모드 | 기본 ON/OFF | URL | 환경 변수 |
|---|---|---|---|
| Dev (`run-dev.sh`) | **ON** | `http://127.0.0.1:8080` | `SQLITE_WEB_ENABLED=1` |
| Prod (`run-prod.sh`) | **OFF** | (필요 시 8080) | `backend.prod.env` 에서 ON 변경 가능 |

관련 환경 변수 (`backend.dev.env` / `backend.prod.env`):

```env
SQLITE_WEB_ENABLED=1        # 0이면 sqlite-web 프로세스 미기동
SQLITE_WEB_HOST=0.0.0.0
SQLITE_WEB_PORT=8080
SQLITE_WEB_READ_ONLY=0      # 1로 두면 read-only 모드
```

방화벽이 필요한 환경에서는 `8080/tcp` 를 dev 서버에서 추가로 허용해야
합니다 (`deploy/GUIDE.md` 참고).

---

## 폴더 구조 (요약)

```
AutoTestManager/
├── backend/                # FastAPI + SQLAlchemy 서버 (자세한 내용은 backend/README.md)
│   ├── app/
│   │   ├── api/            # 라우트 (auth, admin, rtd, ezdfs, mypage)
│   │   ├── core/           # config, security, responses, exceptions
│   │   ├── db/             # SQLAlchemy session + init
│   │   ├── models/         # ORM 엔티티
│   │   ├── schemas/        # Pydantic 스키마
│   │   ├── services/       # orchestrator + *_custom.py 훅
│   │   └── utils/          # enums, constants, ssh_helpers, naming
│   └── data/               # SQLite + results + logs (gitignored)
│
├── frontend/               # Vue 3 SPA (자세한 내용은 frontend/README.md)
│   ├── src/
│   │   ├── views/          # 얇은 쉘 (RTDView, EzDFSView, AdminView …)
│   │   ├── components/     # rtd/, ezdfs/, admin/ 스텝·탭 컴포넌트
│   │   ├── composables/    # useTaskPolling 등 재사용 훅
│   │   ├── stores/         # auth, rtd, ezdfs, admin, ui, theme
│   │   └── styles/         # 토큰/레이아웃/컴포넌트/페이지별 모듈 CSS
│   └── public/
│
├── docs/
│   ├── plan.md             # 상위 기획 문서
│   ├── Back.md             # 백엔드 구현 기준
│   └── Front.md            # 프론트 구현 기준
│
├── CLAUDE.md               # Claude Code 용 프로젝트 가이드
├── env_detail.md           # 배포 환경 / 폐쇄망 제약 메모
└── README.md               # (이 파일)
```

---

## 배포 (개요)

1. 온라인 개발 머신에서 image build
   ```bash
   docker build -t atm-backend:<tag>  backend/
   docker build -t atm-frontend:<tag> frontend/
   docker save atm-backend:<tag>  | gzip > atm-backend.tar.gz
   docker save atm-frontend:<tag> | gzip > atm-frontend.tar.gz
   ```
2. 운영 서버 (RHEL 7.9) 로 tar.gz 이관 → `docker load`
3. `docker run` 시 소스/데이터 디렉토리를 **bind mount**
   - backend: `backend/app` → `/app/app`, `backend/data` → `/app/data`
   - frontend: nginx 가 정적 `dist/` 를 서빙하며 `/api/*` 를 backend 로 프록시

자세한 동작 방식은 각 `Dockerfile` 및 `frontend/nginx.conf` 참조.

---

## 설계 원칙 (요점)

- **Custom 파일 경계**
  모든 SSH 명령과 파일 포맷 파싱은 `services/*_custom.py` 및
  `utils/ssh_helpers.py` 안에서만 발생. orchestrator service 는
  `paramiko` 를 직접 import 하지 않음.
- **뷰는 얇게**
  `views/*.vue` 는 스텝 상태와 레이아웃만 보유. 실제 UI/상호작용은
  `components/{rtd,ezdfs,admin}/` 의 하위 컴포넌트가 담당.
- **세션 복원 우선**
  새로고침 후에도 위저드 진행 상태가 유지되는 것은 고정 요구사항.
  `RuntimeSession` 테이블 + frontend store 가 단계마다 서버와 싱크.
- **폐쇄망 / 오프라인**
  외부 CDN / npm registry 접근 금지. 모든 의존성은 image 에 포함.
- **한국어 UI 레이블 유지**
  기존 한국어 레이블은 함부로 바꾸지 않는다.

---

## 문서 링크

| 대상 | 문서 |
|---|---|
| Claude Code / AI 에이전트 | [`CLAUDE.md`](./CLAUDE.md) |
| 백엔드 상세 | [`backend/README.md`](./backend/README.md) |
| 프론트엔드 상세 | [`frontend/README.md`](./frontend/README.md) |
| 기능 기획 | [`docs/plan.md`](./docs/plan.md) |
| 백엔드 구현 기준 | [`docs/Back.md`](./docs/Back.md) |
| 프론트엔드 구현 기준 | [`docs/Front.md`](./docs/Front.md) |
| 배포 환경 메모 | [`env_detail.md`](./env_detail.md) |

---

## 라이선스

사내용 내부 프로젝트입니다. 외부 공개 배포 용도가 아닙니다.
