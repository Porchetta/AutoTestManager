# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

RTD 및 ezDFS 테스트 흐름을 웹에서 관리하는 `Vue 3 + FastAPI` 기반 테스트 매니저.
개발 환경은 `Windows + WSL` 기준.

## 명령어

### Backend

```bash
cd backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh      # 최초 설정 (.venv 생성, requirements 설치, .env 복사)
./run-dev.sh        # uvicorn으로 실행 (포트 10223, --reload)
```

직접 실행:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 10223
```

- API: `http://127.0.0.1:10223`
- Swagger: `http://127.0.0.1:10223/docs`
- Health: `http://127.0.0.1:10223/health`
- 기본 관리자: `admin` / `admin1234`

### Frontend

```bash
cd frontend
cp .env.example .env   # 최초 1회
npm install
npm run dev            # 포트 4203
npm run build          # 프로덕션 빌드
npm run preview        # 빌드 결과 미리보기 (포트 4173)
```

- Frontend: `http://127.0.0.1:4203`
- 환경 변수: `VITE_API_BASE_URL=http://127.0.0.1:10223`

## 아키텍처

### 전체 구성

```
frontend/   Vue 3 + Vite + Pinia SPA
backend/    FastAPI + SQLAlchemy + SQLite API 서버
docs/       Front.md, Back.md, plan.md (구현 기준 문서)
```

데이터 저장:
- DB: `backend/data/autotestmanager.db`
- 결과 파일: `backend/data/results/`
- 관리자 알람 로그: `backend/data/logs/admin_alert.log`

### Backend 구조 (`backend/app/`)

| 디렉토리 | 역할 |
|---|---|
| `api/` | FastAPI 라우터 (`auth`, `admin`, `rtd`, `ezdfs`, `mypage`) |
| `core/` | 설정(`config.py`), JWT, 보안, 공통 예외 |
| `db/` | SQLAlchemy 세션, 베이스, `init_db()` |
| `models/` | DB 엔티티 |
| `schemas/` | Pydantic 요청/응답 스키마 |
| `services/` | 비즈니스 로직, 실행 훅, 파일 생성 |
| `utils/` | enum (`ActionType`, `TaskStatus`, `TestType`, `TaskStep`) |

**장시간 작업 처리**: 실행 API는 즉시 `task_id`를 반환하고 백그라운드 워커 스레드가 상태를 갱신한다. RTD의 COPY/COMPILE/TEST/RETEST는 타겟별 병렬 실행.

**세션 복원**: RTD / ezDFS step 상태를 DB에 저장. 사용자당 테스트 타입별 1개 세션만 유지.

**API 응답 포맷**: 성공 시 `{"success": true, "data": {...}}`, 파일 다운로드 API만 파일 응답 사용. 모든 prefix는 `/api`.

### Backend 커스텀 포인트 (`backend/app/services/`)

오프라인 환경 적용 시 수정할 파일:

| 파일 | 커스텀 대상 |
|---|---|
| `rtd_catalog_custom.py` | Rule 파일 목록 조회, 파일명 파싱, `.rule` 읽기, Macro 추출 |
| `rtd_execution_custom.py` | 복사, 컴파일, 테스트/재테스트 실행 명령 |
| `rtd_report_custom.py` | 라인별 집계 결과서(`.xlsx`) 생성 |
| `ezdfs_catalog_custom.py` | ezDFS Rule/Module 목록 조회 |
| `ezdfs_execution_custom.py` | ezDFS 테스트 실행 (현재 mock) |
| `ezdfs_report_custom.py` | ezDFS 결과서 생성 (현재 mock) |

RTD 기본 구현 전제:
- Rule 파일: 개발 라인 `home_dir_path`에 위치
- Macro 파일: `../Macro` 상대 경로
- 원격 명령: `bash --noprofile --norc -lc ...`
- 컴파일: `./atm_compiler {rule_name} {line_name}`
- 테스트: `./atm_testscript {rule_name} {line_name}`

### Frontend 구조 (`frontend/src/`)

| 파일/디렉토리 | 역할 |
|---|---|
| `api.js` | Axios 인스턴스, JWT 인터셉터, `apiGet/apiPost/apiPut/apiDelete` 헬퍼 |
| `stores/` | Pinia 스토어 (`auth`, `rtd`, `ezdfs`, `theme`, `ui`) |
| `views/` | 페이지 컴포넌트 (`RTDView`, `EzDFSView`, `AdminView`, `MyPageView`, …) |
| `components/` | 공통 컴포넌트 (`SidebarNav`, `StatusBadge`) |
| `layouts/` | `MainLayout.vue` (Sidebar + 헤더 + 라우터 뷰) |
| `router/` | Vue Router 설정, 인증/관리자 가드 |
| `style.css` | CSS 토큰 기반 디자인 시스템 (라이트/다크 이중 테마) |

**인증 흐름**: 로그인 성공 → JWT + 사용자 정보를 `localStorage`(`atm-auth`) 저장 → Axios 인터셉터에서 `Authorization: Bearer` 자동 첨부 → 401 수신 시 로컬 로그아웃 후 `/login` 이동.

**API 클라이언트**: `api.js`의 `apiGet/apiPost` 등은 `response.data.data`를 바로 반환. 401 자동 처리, 에러 시 전역 Toast(`uiStore.setError`) 호출.

**디자인 시스템**: `style.css`에 CSS 토큰 정의. teal 계열 `--accent` 주요 액센트. `button-primary/secondary/ghost/danger` 클래스, `.status-badge[data-status]` 상태 뱃지 사용.

### 라우팅

- `/login`, `/signup` — 비인증 전용
- `/` — 대시보드 (인증 필요)
- `/rtd` — RTD Test Manager (인증 필요)
- `/ezdfs` — ezDFS Test (인증 필요)
- `/admin` — Admin (관리자 권한 필요)
- `/mypage` — My Page (인증 필요)

## 구현 현황

- **RTD**: SSH 기반 조회/실행 구조 완성. 6단계 매니저(사업부 → 개발 라인 → Rule → Macro → 타겟 → 실행).
- **ezDFS**: 현재 mock/단순 생성 로직. test/retest/raw/summary 흐름은 유지하되 추후 실제 연동으로 교체.
- 결과서 최종 운영 포맷 미확정 (현재 `.xlsx` 단순 생성).

## 참조 문서

- `docs/Front.md` — 프론트 구현 기준 (컴포넌트별 상세 동작 기준)
- `docs/Back.md` — 백엔드 구현 기준 (API 계약, 정책 우선 기준)
- `docs/plan.md` — 상위 기획 문서
