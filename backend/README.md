# AutoTestManager — Backend

FastAPI + SQLAlchemy 2.0 + SQLite 기반의 API 서버.
폐쇄망(RHEL 7.9) 환경에서 Paramiko 로 원격 호스트에 SSH 접속해서
RTD / ezDFS rule 테스트를 수행하고, openpyxl 로 `.xlsx` 결과서를 만듭니다.

> 상위 프로젝트 개요는 [루트 README](../README.md), 전체 아키텍처 가이드는
> [`CLAUDE.md`](../CLAUDE.md) 를 참고하세요.

---

## 빠른 시작

```bash
cd backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh   # .venv 생성 + requirements.txt 설치 (uv 우선, 없으면 venv+pip)
./run-dev.sh     # uvicorn --reload, port 10223
```

| | |
|---|---|
| API | `http://127.0.0.1:10223` |
| Swagger | `http://127.0.0.1:10223/docs` |
| Health | `http://127.0.0.1:10223/health` |

첫 기동 시 `bootstrap.seed_admin()` 이 기본 관리자 계정을 생성합니다.

- `user_id`: `admin`
- `password`: `admin1234`

---

## 기술 스택

| 레이어 | 사용 |
|---|---|
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0 (`Mapped[...]` + `mapped_column()`) |
| Validation | Pydantic v2 (`model_config = ConfigDict(from_attributes=True)`) |
| DB | SQLite (`backend/data/autotestmanager.db`) |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| SSH | Paramiko |
| Excel | openpyxl |
| Config | pydantic-settings (`.env` 로딩) |

백그라운드 작업은 **daemon thread** 로 처리합니다 (Celery / RQ 등 외부
브로커 없음). 폐쇄망 제약 때문에 외부 패키지 추가는 항상 image build 후
이관까지 고려해서 결정합니다.

---

## 디렉토리 레이아웃

```
backend/
├── Dockerfile
├── dev-setup.sh / run-dev.sh       # 로컬 개발 헬퍼
├── requirements.txt
├── data/                           # SQLite + results + logs (gitignored)
└── app/
    ├── main.py                     # FastAPI 앱, lifespan, CORS, router 등록
    │                                # core/exceptions 의 예외 핸들러 등록
    │
    ├── api/                        # 얇은 컨트롤러 — 검증/요청만 처리
    │   ├── auth.py                 # /api/auth/* (signup, login, password)
    │   ├── admin.py                # /api/admin/* (users, hosts, configs)
    │   ├── rtd.py                  # /api/rtd/* (catalog, session, execute, download)
    │   ├── ezdfs.py                # /api/ezdfs/*
    │   ├── mypage.py               # /api/mypage/* (이력/결과)
    │   └── deps.py                 # get_db, get_current_user, require_admin
    │
    ├── core/
    │   ├── config.py               # Settings (cors_origins, jwt, paths …)
    │   ├── security.py             # JWT encode/decode, 패스워드 해싱
    │   ├── responses.py            # success_response() 래퍼
    │   └── exceptions.py           # 도메인 예외 + FastAPI handler
    │
    ├── db/
    │   └── session.py              # Engine, SessionLocal, Base, init_db,
    │                                # _ensure_legacy_columns() (임시 마이그레이션)
    │
    ├── models/
    │   └── entities.py             # User, HostConfig, HostCredential, RtdConfig,
    │                                # EzdfsConfig, TestTask, RuntimeSession,
    │                                # DashboardLike
    │
    ├── schemas/                    # Pydantic 입출력 스키마 (API 단위로 분리)
    │
    ├── services/                   # 도메인 로직 — 두 계층으로 나뉨
    │   │
    │   │ (1) Orchestrator — SSH / 파싱 로직 금지
    │   ├── catalog_service.py      # RTD/ezDFS catalog 조회 조정
    │   ├── task_service.py         # TestTask CRUD 및 상태 전이
    │   ├── task_worker.py          # daemon thread 기반 실행 루프
    │   ├── task_queue.py           # line/module 단위 직렬화 Queue
    │   ├── file_service.py         # raw / summary 파일 생성 지점
    │   ├── file_download.py        # 최신 결과 집계 / 다운로드 경로 결정
    │   ├── session_service.py      # RuntimeSession 저장/복원
    │   ├── ssh_runtime.py          # SSHConnectionPool + 병렬 제한 감지
    │   └── bootstrap.py            # seed admin, 결과 디렉토리 준비
    │   │
    │   │ (2) Custom hooks — 오프라인 환경 적응 지점
    │   ├── rtd_catalog_custom.py
    │   ├── rtd_execution_custom.py
    │   ├── rtd_report_custom.py
    │   ├── ezdfs_catalog_custom.py
    │   ├── ezdfs_execution_custom.py
    │   ├── ezdfs_report_custom.py
    │   └── svn_upload_custom.py
    │
    └── utils/
        ├── enums.py                # TestType, ActionType, TaskStatus, TaskStep
        ├── constants.py            # TARGET_SUFFIX, RULE_ERROR_ITEM, BASH_PREFIX …
        ├── ssh_helpers.py          # build_clean_bash_command, run_remote_command,
        │                             # extract_session_payload
        └── naming.py               # normalize_target_line_name
```

---

## 핵심 아키텍처 — 3 계층 + Custom 훅

폐쇄망 환경마다 원격 서버의 디렉토리 구조, 명령, 파일 포맷이 달라지기 때문에
**orchestrator 와 custom 훅을 물리적으로 분리**해서 운영합니다.

```
         ┌────────────────────────────┐
HTTP ──▶ │ api/*.py  (thin router)    │
         └──────────────┬─────────────┘
                        │  ORM session + auth + schema 검증
                        ▼
         ┌────────────────────────────┐
         │ services/*_service.py       │  ← orchestrator
         │ services/task_worker.py     │     SSH / 파싱 로직 없음
         │ services/file_*.py          │
         └──────────────┬─────────────┘
                        │  domain intent
                        ▼
         ┌────────────────────────────┐
         │ services/*_custom.py        │  ← 커스터마이즈 지점
         │ + utils/ssh_helpers.py      │     (여기서만 paramiko 사용)
         └──────────────┬─────────────┘
                        │  bash over SSH
                        ▼
                   원격 호스트
```

### 각 단계별 호출 체인

```
Catalog  :  api/rtd.py       → catalog_service.py    → rtd_catalog_custom.py    → ssh_helpers
Execute  :  api/rtd.py       → task_service.py       → task_worker.py           → rtd_execution_custom.py   → ssh_helpers
                                                                                 → svn_upload_custom.py
Report   :  api/mypage.py    → file_service.py       → rtd_report_custom.py     → openpyxl
Download :  api/mypage.py    → file_download.py      → (파일 경로 결정 + 반환)
```

**규칙**:
- `catalog_service` / `task_service` / `task_worker` / `file_service` /
  `file_download` 는 `paramiko` 를 **import 금지**
- SSH 명령은 전부 `ssh_helpers.build_clean_bash_command()` 로 감싸서
  `bash --noprofile --norc -lc '<quoted>'` 형식으로 실행
- rule 텍스트 파싱 / 파일명 규칙 / 원격 디렉토리 계산은 `*_custom.py` 안에서만

---

## Custom 훅 설명

`*_custom.py` 파일은 폐쇄망 환경에 맞게 **사업부 별로 교체**되는 훅입니다.
세 계층(Catalog / Execution / Report) + SVN 업로드로 나뉩니다.

### Catalog — `rtd_catalog_custom.py` / `ezdfs_catalog_custom.py`
| 함수 | 역할 |
|---|---|
| `fetch_rule_source_file_names(...)` | 원격 서버의 rule 소스 파일 목록 조회 |
| `parse_rule_catalog_entries(...)` | 파일명에서 `rule_name`, `version` 추출 |
| `read_rule_source_text(...)` | rule 소스 텍스트 읽기 |
| `extract_macro_list(...)` *(RTD)* | old/new `.report` 비교 Macro 리스트 |
| `extract_sub_rule_list_from_rule_text(...)` *(ezDFS)* | Sub Rule 리스트 |

### Execution — `rtd_execution_custom.py` / `ezdfs_execution_custom.py`
| 함수 | 역할 |
|---|---|
| `execute_copy_action(...)` | Rule 파일을 타겟 라인으로 복사 |
| `execute_compile_action(...)` | `./atm_compiler ...` 실행 |
| `execute_test_action(...)` *(RTD)* | `./atm_testscript ...` 실행 |
| `execute_ezdfs_test_action(...)` | ezDFS 테스트 실행 |

### Report — `rtd_report_custom.py` / `ezdfs_report_custom.py`
| 함수 | 역할 |
|---|---|
| `build_rtd_test_report_file(...)` | 선택 라인 최신 결과 → `.xlsx` |
| `build_ezdfs_test_report_file(...)` | 동일 (ezDFS) |

### SVN — `svn_upload_custom.py`
| 함수 | 역할 |
|---|---|
| `perform_svn_upload(...)` | `svn ci -m ...` 체크인 흐름 |

---

## 백그라운드 실행 모델

```
  api 요청
      │
      ▼
  task_service.create_task()         ── DB 에 TestTask INSERT
      │
      ▼
  task_queue.enqueue(line/module)    ── threading.Condition 기반 in-memory queue
      │                                  · RTD: line 단위 직렬화
      │                                  · ezDFS: module 단위 직렬화
      ▼
  task_worker (daemon thread)        ── 각 queue 당 워커 1개
      │  · 자체 DB session 오픈 (request-scoped 사용 금지)
      │  · *_execution_custom 호출
      │  · 상태 전이 (QUEUED → RUNNING → DONE/FAIL/CANCELED)
      │  · raw 출력 파일을 data/results/... 로 저장
      ▼
  DB + results/
```

워커 루프 최상단의 `except Exception` 과 SSH 병렬 감지 fallback 의
`except Exception` 은 **의도적인 광범위 catch** 입니다. 그 외에는 모두
`paramiko.SSHException`, `json.JSONDecodeError`, `OSError` 등 **구체적**
예외 타입을 잡습니다.

---

## 설정 (`core/config.py`)

`.env` → `Settings` 로 로드됩니다. 주요 항목:

| 키 | 기본값 | 설명 |
|---|---|---|
| `JWT_SECRET_KEY` | (필수) | JWT 서명 키 |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | |
| `DATABASE_URL` | `sqlite:///./data/autotestmanager.db` | |
| `CORS_ORIGINS` | `http://localhost:4203` | 쉼표 구분 리스트 |
| `ADMIN_ALERT_LOG` | `./data/logs/admin_alert.log` | SSH 감지 실패 알람 파일 |

`CORS_ORIGINS=http://localhost:4203,http://prod.example.com` 같은 식으로
운영 URL 을 추가할 수 있습니다 (Phase 1.5).

---

## 예외 처리 (`core/exceptions.py`)

| 예외 | HTTP 상태 | 쓰임 |
|---|---|---|
| `ConfigNotFoundError` | 404 | RTD/ezDFS config 미존재 |
| `TaskConflictError` | 409 | 동일 line/module 중복 실행 시도 |
| `CatalogError` | 400 | 원격에서 catalog 를 읽지 못함 |
| `SSHConnectionError` | 502 | Paramiko 연결 실패 |
| `RemoteCommandError` | 502 | 원격 명령 비정상 종료 |

`main.py` 에서 각 예외별 handler 가 등록되어 응답 payload 를
`{"success": false, "error": {"code": ..., "message": ..., "detail": {...}}}`
로 정규화합니다.

---

## 데이터 저장 규칙

```
backend/data/
├── autotestmanager.db                 # SQLite
├── logs/admin_alert.log               # SSH 감지 실패 등 관리자 알람
└── results/
    ├── rtd/
    │   ├── raw/{user_id}/             # 라인별 raw 출력 txt + index.json
    │   ├── {task_id}/                 # task 별 summary xlsx
    │   └── reports/{user_id}/         # 사업부별 집계 xlsx
    └── ezdfs/
        ├── raw/{user_id}/
        └── reports/{user_id}/
```

- DB 에는 **결과 본문이 아니라 파일 경로**만 저장
- 다운로드 파일명은 저장 시 파일명을 그대로 사용
- monitor 의 Raw Data 다운로드는 **현재 로그인 사용자의 최신 TEST/RETEST**
  결과에만 활성화

---

## 코딩 컨벤션

- 모든 모듈 최상단에 `from __future__ import annotations`
- SQLAlchemy 모델은 `Mapped[type]` + `mapped_column()` 패턴
- Pydantic 모델은 `model_config = ConfigDict(from_attributes=True)`
- API 응답은 `success_response({...})` 로 감싼다
- 원격 명령은 반드시 `ssh_helpers.build_clean_bash_command()` 를 통해 생성
- 시간은 전부 UTC (`datetime.now(timezone.utc)`)
- 문자열 상태값은 `utils/enums.py` 의 `TestType` / `ActionType` /
  `TaskStatus` / `TaskStep`

---

## 개발 중 자주 쓰는 명령

```bash
# 가상환경 활성화
source .venv/bin/activate

# 패키지 재설치 (requirements 변경 시)
./dev-setup.sh

# 서버 기동
./run-dev.sh

# DB 초기화 (주의: 결과 파일은 남는다)
rm -f data/autotestmanager.db
./run-dev.sh  # 기동 시 init_db + seed_admin 다시 실행됨
```

---

## 알려진 / 의도적인 동작

- **legacy column 보정**: `db/session.py::_ensure_legacy_columns()` 가
  기존 DB 를 쓰는 경우 누락 컬럼을 ALTER 로 추가합니다. Alembic 전환은
  [`CLAUDE.md` Phase 3.3](../CLAUDE.md) 항목으로 남아있습니다.
- **기본 관리자 seed**: 처음 기동 시 항상 `admin` / `admin1234` 가 만들어집니다.
  운영 서버에 올리기 전에 반드시 비밀번호 변경이 필요합니다.
- **SSH 병렬 제한 감지 실패**: 원격 `sshd_config` 를 읽지 못한 경우
  기본값 `10` 을 사용하고 `admin_alert.log` 에 기록합니다.

---

## 더 읽을거리

- [상위 README](../README.md) — 프로젝트 개요
- [`../CLAUDE.md`](../CLAUDE.md) — 전체 아키텍처 / 리팩토링 로드맵
- [`../docs/Back.md`](../docs/Back.md) — API 계약 상세 (한글)
- [`../docs/plan.md`](../docs/plan.md) — 기획 요구사항 (한글)
