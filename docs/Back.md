# AutoTestManager Backend Reference

## 1. 문서 목적
이 문서는 `docs/plan.md`, `docs/Front.md`를 기준으로 현재 구현된 AutoTestManager 백엔드의 기준 동작을 정리한 문서다.

목표는 다음 3가지를 명확히 하는 것이다.
- 백엔드가 반드시 구현해야 하는 기능 범위
- 프론트엔드와 맞춰야 하는 실제 API 계약
- 이후 오프라인 환경에서 커스텀할 기능 범위와 현재 `mock` 유지 범위

이 문서는 설명용이 아니라 구현 기준 문서다.  
애매하면 본 문서의 정책을 우선 적용한다.

## 2. 구현 목표
- FastAPI 기반 REST API 제공
- JWT 인증 및 관리자 권한 분리
- SQLite 기반 데이터 저장
- RTD / ezDFS 테스트 실행 흐름 관리
- 장시간 작업 상태 추적
- 테스트 결과 메타데이터 저장
- 새로고침 이후에도 세션 복원 가능하도록 서버 측 세션 상태 저장
- Docker 이미지 빌드 및 오프라인 배포 가능 구조 유지

## 3. 기술 스택
- Framework: FastAPI
- Database: SQLite
- ORM: SQLAlchemy 2.x
- Validation: Pydantic
- Auth: JWT Access Token
- Password Hashing: `passlib` + `bcrypt`
- Build: Docker

## 4. 구현 범위와 비범위

### 4.1 이번 구현 범위
- 인증 API
- 관리자 설정 CRUD API
- RTD 조회 / 세션 / 실행 / 상태 API
- ezDFS 조회 / 세션 / 실행 / 상태 API
- My Page 최근 이력 API
- 결과 파일 메타데이터 저장 API
- 결과 파일 다운로드 / 결과서 생성 기능

### 4.2 이번 구현에서 mock 처리할 기능
현재 기준 mock 또는 단순 생성 로직으로 유지하는 기능은 아래와 같다.
- ezDFS 테스트 요청
- ezDFS RawData 다운로드(`.txt`)
- ezDFS 테스트 결과서 생성 / 다운로드(`.xlsx`)
- RTD 개별 task summary 생성(`POST /api/rtd/results/{task_id}/summary`)

### 4.3 이번 구현에서 하지 않는 것
- 외부 리포트 엔진 연동
- 고정된 오프라인 환경 전용 파일명 파싱 규칙 강제
- 최종 운영 포맷의 RTD 결과서 레이아웃

즉, 현재 단계에서는 "동작하는 백엔드 인터페이스 + 커스텀 가능한 SSH 기반 실행 훅 + 파일 산출물 생성"이 목표다.

## 5. 권장 프로젝트 구조
- `app/main.py`
- `app/api/`
  - `auth.py`
  - `admin.py`
  - `rtd.py`
  - `ezdfs.py`
  - `mypage.py`
- `app/core/`
  - 설정, 보안, JWT, 예외 처리, 공통 응답
- `app/db/`
  - 세션, 베이스, 초기화
- `app/models/`
  - DB 모델
- `app/schemas/`
  - 요청 / 응답 스키마
- `app/services/`
  - 인증, 관리자 로직, 테스트 실행, 파일 생성

## 6. 핵심 설계 원칙

### 6.1 API 정책
- 모든 API prefix는 `/api` 사용
- 응답은 JSON을 기본으로 한다
- 다운로드 API만 파일 응답 사용
- 목록 API는 프론트에서 바로 쓰기 쉽게 paging 없는 단순 구조로 제공한다

### 6.2 인증 정책
- 로그인 성공 시 JWT access token 발급
- 보호 API는 Bearer Token 필요
- 관리자 API는 `is_admin = true` 필요
- `is_approved = false` 사용자는 로그인 불가

### 6.3 세션 복원 정책
- RTD / ezDFS step 상태는 서버 저장소에 보관한다
- 현재 구현은 DB 기반 세션 저장 구조를 사용한다
- 사용자당 테스트 타입별 1개 세션만 유지한다

### 6.4 장시간 작업 정책
- 실행 API는 즉시 완료하지 않는다
- 요청 시 `task_id`를 반환하고 실제 상태는 background worker thread가 갱신한다
- RTD의 `COPY`, `COMPILE`, `TEST`, `RETEST`는 타겟별 worker thread로 병렬 실행할 수 있다
- ezDFS는 현재 mock background task 기반 흐름을 유지한다

## 7. 공통 응답 규칙

### 7.1 성공 응답

```json
{
  "success": true,
  "data": {}
}
```

### 7.2 실패 응답

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "사용자에게 보여줄 메시지",
    "detail": {}
  }
}
```

### 7.3 HTTP status 정책
- `200 OK`: 조회, 수정 성공
- `201 Created`: 생성 성공
- `204 No Content`: 삭제 성공
- `400 Bad Request`: 잘못된 흐름 요청
- `401 Unauthorized`: 인증 실패
- `403 Forbidden`: 권한 없음
- `404 Not Found`: 대상 없음
- `409 Conflict`: 중복 실행, 중복 이름, 참조 중 삭제 시도
- `422 Unprocessable Entity`: 입력 검증 실패
- `500 Internal Server Error`: 내부 오류

## 8. 데이터 모델

### 8.1 users
- `id`
- `user_id`
- `password_hash`
- `user_name`
- `module_name`
- `is_admin`
- `is_approved`
- `created_at`
- `updated_at`

정책:
- `user_id`는 unique
- 로그인 식별자는 `user_id`

### 8.2 host_configs
- `id`
- `name`
- `ip`
- `login_user`
- `login_password`
- `modifier`
- `ssh_parallel_limit`
- `ssh_parallel_limit_source`
- `created_at`
- `updated_at`

정책:
- `name`은 unique
- `modifier`는 수동 입력을 받지 않고 로그인한 관리자 `user_name`을 자동 저장한다
- `ssh_parallel_limit`은 host 등록 / 수정 또는 관리자 수동 감지 시 갱신한다
- 감지 실패 시 기본값 `10`을 사용하고 `ssh_parallel_limit_source`는 `default`로 저장할 수 있다

### 8.3 rtd_configs
- `id`
- `line_name`
- `line_id`
- `business_unit`
- `home_dir_path`
- `host_name`
- `modifier`
- `created_at`
- `updated_at`

정책:
- `line_name`은 unique
- `host_name`은 `host_configs.name` 참조
- `modifier`는 수동 입력을 받지 않고 로그인한 관리자 `user_name`을 자동 저장한다

### 8.4 ezdfs_configs
- `id`
- `module_name`
- `port`
- `home_dir_path`
- `host_name`
- `modifier`
- `created_at`
- `updated_at`

정책:
- `module_name`은 unique
- `host_name`은 `host_configs.name` 참조
- `modifier`는 수동 입력을 받지 않고 로그인한 관리자 `user_name`을 자동 저장한다

### 8.5 test_tasks
- `id`
- `task_id`
- `test_type`
- `action_type`
- `user_id`
- `target_name`
- `status`
- `current_step`
- `message`
- `requested_payload_json`
- `raw_result_path`
- `summary_result_path`
- `requested_at`
- `started_at`
- `ended_at`
- `created_at`
- `updated_at`

설명:
- `test_type`: `RTD`, `EZDFS`
- `action_type`: `COPY`, `COMPILE`, `TEST`, `RETEST`, `GENERATE_SUMMARY`
- `target_name`: RTD는 line name, ezDFS는 module name
- `raw_result_path`, `summary_result_path`는 실제 파일 경로를 저장한다
- raw data 본문과 결과서 본문 자체는 DB가 아니라 파일시스템에 저장한다

### 8.6 runtime_sessions
- `id`
- `user_id`
- `session_type`
- `payload_json`
- `updated_at`

정책:
- `session_type`: `RTD`, `EZDFS`
- `(user_id, session_type)` unique

## 9. Enum 정의

### 9.1 공통 상태
- `PENDING`
- `RUNNING`
- `DONE`
- `FAIL`
- `CANCELED`

### 9.2 RTD 상세 단계 상태
- `READY`
- `COPYING`
- `COMPILING`
- `TESTING`

### 9.3 ezDFS 상세 단계 상태
- `READY`
- `TESTING`

## 10. 커스텀 / 파일 생성 정책

### 10.1 커스텀 포인트
RTD는 아래 3개 파일을 기준으로 오프라인 환경 맞춤 구현이 가능해야 한다.
- `app/services/rtd_catalog_custom.py`
  - Rule source file 목록 조회
  - 파일명 파싱으로 `rule_name`, `version` 생성
  - `.rule` 파일 텍스트 읽기
  - Rule 텍스트에서 Macro list 추출
- `app/services/rtd_execution_custom.py`
  - 복사
  - 컴파일
  - 테스트 / 재테스트
- `app/services/rtd_report_custom.py`
  - 선택된 라인의 최신 테스트 결과를 모아 집계 결과서 생성

원칙:
- API 계약은 유지한다
- 내부 구현은 오프라인 환경에 맞춰 교체 가능해야 한다
- 커스텀 시에도 `task.status`, `message`, 결과 파일 저장 규칙은 유지하는 것을 권장한다

### 10.2 RTD 실행 기본 구현
현재 기본 구현은 아래와 같다.
- Rule / Version 조회: 개발 라인의 `host_name`, `home_dir_path` 기준 SSH 접속
- Macro 비교: `.rule` 파일 내용을 읽고, nested macro 파일까지 재귀적으로 탐색
- 복사: 개발 라인 `home_dir_path`에서 타겟 라인 `home_dir_path`로 Rule 파일 복사
- Macro 복사: 개발 라인 `../Macro`에서 타겟 라인 `../Macro`로 복사
- 컴파일: 타겟 라인 디렉터리에서 `./atm_compiler {rule_name} {line_name}` 실행
- 테스트 / 재테스트: 타겟 라인 디렉터리에서 `./atm_testscript {rule_name} {line_name}` 실행
- 개발 라인 자체는 복사 대상에서 제외한다

SSH 명령 실행 정책:
- 원격 명령은 `bash --noprofile --norc -lc ...` 형식으로 실행한다
- 사용자 프로필 / rc 로딩에 의해 `env.fish` 등 외부 초기화 스크립트 오류가 끼어들지 않도록 한다
- host별 SSH 병렬 제한은 원격 `sshd -T` 결과의 `maxstartups`를 우선 사용한다
- 병렬 제한 감지 실패 시 기본값 `10`을 사용한다
- 감지 실패는 `/data/logs/admin_alert.log`에 기록한다

### 10.3 파일 생성 규칙
- RawData 파일은 `.txt`
- 개별 task summary 파일은 `.xlsx`
- 집계 테스트 결과서는 `.xlsx`

저장 규칙:
- RTD raw data
  - `/data/results/rtd/raw/{user_id}/{line_name}-{timestamp}.txt`
- RTD 개별 task summary
  - `/data/results/rtd/{task_id}/rtd_{task_id}_summary.xlsx`
- RTD 집계 테스트 결과서
  - `/data/results/rtd/reports/{user_id}/{business_unit}-{timestamp}.xlsx`
- ezDFS raw / summary
  - 기존 task 단위 저장 구조 유지

다운로드 정책:
- 실제 저장된 파일명을 그대로 다운로드 파일명으로 사용한다
- 브라우저 다운로드를 위해 `Content-Disposition` 헤더를 노출한다

### 10.4 파일 내용 정책
- RTD RawData txt
  - `task_id`
  - `test_type`
  - `action_type`
  - `target_name`
  - `status`
  - `requested_at`
  - 실제 test script stdout / stderr 또는 기본 로그
- RTD 집계 결과서 xlsx
  - 기본 구현은 타겟 라인별 최신 테스트 task 메타데이터와 raw path를 한 시트에 정리한다
  - 최종 운영 레이아웃은 `rtd_report_custom.py`에서 교체 가능하다

## 11. 인증 API

### 11.1 회원가입
- `POST /api/auth/signup`

request:
```json
{
  "user_id": "mss01",
  "password": "password",
  "user_name": "홍길동",
  "module_name": "MSS"
}
```

정책:
- 가입 후 `is_approved = false` 기본 생성

### 11.2 로그인
- `POST /api/auth/login`

request:
```json
{
  "user_id": "mss01",
  "password": "password"
}
```

response:
```json
{
  "success": true,
  "data": {
    "access_token": "jwt-token",
    "token_type": "bearer",
    "user": {
      "user_id": "mss01",
      "user_name": "홍길동",
      "module_name": "MSS",
      "is_admin": false,
      "is_approved": true
    }
  }
}
```

### 11.3 로그아웃
- `POST /api/auth/logout`

정책:
- 현재 구현은 서버측 blacklist 없이 no-op 처리 가능

### 11.4 비밀번호 변경
- `PUT /api/auth/password`

### 11.5 내 정보 조회
- `GET /api/auth/me`

### 11.6 초기 관리자 계정
- 서버 시작 시 환경변수 기준 기본 관리자 계정을 seed할 수 있다

## 12. Admin API

관리자 API는 모두 관리자 권한 필요.

### 12.1 User Management
- `GET /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `PUT /api/admin/users/{user_id}/approve`
- `PUT /api/admin/users/{user_id}/reject`
- `PUT /api/admin/users/{user_id}/role`
- `DELETE /api/admin/users/{user_id}`

실제 프론트 기본 사용 API:
- `PUT /api/admin/users/{user_id}`

request:
```json
{
  "module_name": "MSS",
  "is_admin": true,
  "is_approved": true
}
```

비고:
- `/approve`, `/reject`, `/role`는 호환용으로 유지할 수 있으나, 현재 프론트는 인라인 편집 후 통합 update API를 사용한다.

### 12.2 Host Settings
- `GET /api/admin/hosts`
- `POST /api/admin/hosts`
- `PUT /api/admin/hosts/{name}`
- `DELETE /api/admin/hosts/{name}`

`POST /api/admin/hosts` request:
```json
{
  "name": "HOST_A",
  "ip": "10.10.10.10",
  "login_user": "tester",
  "login_password": "password"
}
```

`PUT /api/admin/hosts/{name}` request:
```json
{
  "name": "HOST_A",
  "ip": "10.10.10.11",
  "login_user": "tester2",
  "login_password": "password2"
}
```

정책:
- `modifier`는 request로 받지 않는다
- 생성 / 수정 시 현재 로그인한 관리자 `user_name`으로 자동 저장한다
- host 이름 변경 시 참조 중인 `rtd_configs.host_name`, `ezdfs_configs.host_name`도 함께 갱신한다
- 삭제 시 참조 중이면 `409 Conflict`

### 12.3 RTD Settings
- `GET /api/admin/rtd/configs`
- `POST /api/admin/rtd/configs`
- `PUT /api/admin/rtd/configs/{line_name}`
- `DELETE /api/admin/rtd/configs/{line_name}`

`POST /api/admin/rtd/configs` request:
```json
{
  "line_name": "LINE_A",
  "line_id": "1001",
  "business_unit": "MSS",
  "home_dir_path": "/home/rtd/LINE_A",
  "host_name": "HOST_A"
}
```

`PUT /api/admin/rtd/configs/{line_name}` request:
```json
{
  "line_name": "LINE_A",
  "line_id": "1002",
  "business_unit": "MSS",
  "home_dir_path": "/home/rtd/LINE_A_NEW",
  "host_name": "HOST_A"
}
```

정책:
- `modifier`는 request로 받지 않는다
- 생성 / 수정 시 현재 로그인한 관리자 `user_name`으로 자동 저장한다
- `host_name`은 등록된 host를 참조해야 한다

### 12.4 ezDFS Settings
- `GET /api/admin/ezdfs/configs`
- `POST /api/admin/ezdfs/configs`
- `PUT /api/admin/ezdfs/configs/{module_name}`
- `DELETE /api/admin/ezdfs/configs/{module_name}`

`POST /api/admin/ezdfs/configs` request:
```json
{
  "module_name": "EZDFS_A",
  "port": 22,
  "home_dir_path": "/home/ezdfs/A",
  "host_name": "HOST_A"
}
```

`PUT /api/admin/ezdfs/configs/{module_name}` request:
```json
{
  "module_name": "EZDFS_A",
  "port": 2222,
  "home_dir_path": "/home/ezdfs/A_NEW",
  "host_name": "HOST_A"
}
```

정책:
- `modifier`는 request로 받지 않는다
- 생성 / 수정 시 현재 로그인한 관리자 `user_name`으로 자동 저장한다
- `host_name`은 등록된 host를 참조해야 한다

## 13. RTD API

### 13.1 조회 API
- `GET /api/rtd/business-units`
- `GET /api/rtd/lines?business_unit={value}`
- `GET /api/rtd/rules?line_name={value}`
- `POST /api/rtd/macros/compare`
- `GET /api/rtd/versions/rules?rule_name={value}&line_name={value}`
- `GET /api/rtd/target-lines?business_unit={value}`

정책:
- 개발 라인 선택 후 Rule / Version 목록은 RTD 설정의 `host_name`, `home_dir_path`를 기준으로 실제 개발 서버에 SSH 접속해 조회한다
- 조회 결과는 사용자별 RTD 세션 payload의 `catalog_cache`에 저장한다
- `catalog_cache`에는 최소 아래 정보가 포함된다
  - `line_name`
  - `files`
  - `rules`
  - `versions`
  - `error`
- `files` 항목은 아래 구조를 사용한다
```json
{
  "file_name": "RULE_A_PC1.0.0.rule",
  "rule_name": "RULE_A",
  "version": "1.0.0"
}
```
- `version`은 세션 저장 시 `.rule` 접미사를 제거한 값으로 저장한다
- Rule 또는 Version 조회 실패 시 `rules`는 `["error"]`를 반환할 수 있다

Rule / Version 파싱 정책:
- SSH 접속 후 `home_dir_path`로 이동한다
- 해당 디렉터리의 파일 목록을 읽는다
- 파일명에 `_PC`가 포함된 경우
  - `_PC` 앞부분은 `rule_name`
  - `_PC` 뒷부분은 `version`
- `version` 저장 시 `.rule`은 제거한다
- 위 규칙은 `rtd_catalog_custom.py`에서 교체 가능하다

### 13.1.1 Macro 비교 정책
- `POST /api/rtd/macros/compare`는 Step 3에서 선택한 Rule target 목록을 받아 old/new rule 파일을 비교한다
- 각 Rule target에 대해 세션 cache에서 `rule_name + version`으로 원본 `file_name`을 찾는다
- 해당 파일을 SSH로 읽어 `.rule` 파일 내용을 가져온다
- macro list는 파일 내용을 줄 단위로 파싱해서 생성한다
- 빈 줄은 제외한다
- `//`, `#`, `;`로 시작하는 주석 줄은 제외한다
- 줄 끝 주석 제거 후 남은 텍스트를 macro 항목으로 사용한다
- macro 안에 또 다른 macro가 있을 수 있으므로 `../Macro` 디렉터리의 macro 파일을 재귀적으로 읽어 확장한다
- 순환 참조는 visited 집합으로 방지한다
- old file과 new file 내용이 다른 경우에만 old/new macro 차이를 계산한다
- 응답 예시:
```json
{
  "success": true,
  "data": {
    "searched": true,
    "old_macros": ["MACRO_A", "MACRO_B"],
    "new_macros": ["MACRO_C"],
    "has_diff": true,
    "error": ""
  }
}
```

### 13.2 세션 API
- `GET /api/rtd/session`
- `PUT /api/rtd/session`
- `DELETE /api/rtd/session`

`PUT /api/rtd/session` payload 예시:
```json
{
  "current_step": 6,
  "selected_business_unit": "MSS",
  "selected_line_name": "LINE_A",
  "selected_rules": ["RULE_01", "RULE_02"],
  "selected_rule_targets": [
    {
      "rule_name": "RULE_01",
      "old_version": "1.0.0",
      "new_version": "1.1.0"
    }
  ],
  "macro_review": {
    "searched": true,
    "old_macros": ["MACRO_A"],
    "new_macros": ["MACRO_B"],
    "has_diff": true,
    "error": ""
  },
  "selected_macros": ["MACRO_A", "MACRO_B"],
  "target_lines": ["LINE_B", "LINE_C"],
  "active_task_ids": ["task-001", "task-002"]
}
```

정책:
- `catalog_cache`는 Rule / Version SSH 조회 결과를 담는 내부 세션 데이터다
- 일반 세션 저장 시 같은 `selected_line_name`이면 기존 `catalog_cache`를 유지한다
- `selected_macros`는 Step 4에서 사용자가 체크한 macro 목록만 저장한다

### 13.3 실행 제어 API
- `POST /api/rtd/actions/copy`
- `POST /api/rtd/actions/compile`
- `POST /api/rtd/actions/test`
- `POST /api/rtd/actions/retest`

공통 응답 예시:
```json
{
  "success": true,
  "data": {
    "task_id": "task-20260409-0001",
    "status": "PENDING"
  }
}
```

정책:
- 요청 시 타겟 라인별 `test_task`를 생성한다
- 각 task는 별도 background worker thread에서 실행한다
- 현재 구현은 `COPY`, `COMPILE`, `TEST`, `RETEST` 모두 타겟별 병렬 실행을 허용한다
- 동일 사용자 + 동일 action + 동일 target + `PENDING/RUNNING` 상태면 `409 Conflict`
- 실제 내부 동작은 `rtd_execution_custom.py`를 통해 수행한다
- `COPY` 요청에서는 `selected_line_name`과 동일한 개발 라인을 자동 제외한다

### 13.4 상태 API
- `GET /api/rtd/status`
- `GET /api/rtd/status/{task_id}`
- `GET /api/rtd/monitor?target_lines={comma-separated}`

`GET /api/rtd/monitor` 정책:
- 선택된 타겟 라인별 상태 카드를 만들기 위한 monitor 응답을 반환한다
- 각 라인에 대해 아래 정보를 제공한다
  - 현재 상태 텍스트
  - 최근 `복사`
  - 최근 `컴파일`
  - 최근 `테스트`
  - RawData 다운로드 가능 여부
- `복사` 상태는 현재 페이지 수명 동안만 보이는 프론트 정책이 적용될 수 있다
- 현재 상태 텍스트는 프론트에서 아래 형태의 chip으로 표시할 수 있다
  - `Copying [이름]`
  - `Compiling [이름]`
  - `Testing [이름]`
  - `대기 [이름]`
- 개발 라인 카드라도 monitor 대상에는 포함될 수 있지만, `복사` 액션은 비활성 표시 대상이다

### 13.5 결과 API
- `GET /api/rtd/results/{task_id}/raw`
- `POST /api/rtd/results/{task_id}/summary`
- `GET /api/rtd/results/{task_id}/summary`
- `GET /api/rtd/results/aggregate-summary?target_lines={comma-separated}`

정책:
- `GET /raw`: 실제 저장된 raw txt 파일 다운로드
- `POST /summary`: 개별 task 기준 단순 summary xlsx 생성
- `GET /summary`: 생성된 개별 xlsx 다운로드
- `GET /aggregate-summary`: 선택된 타겟 라인의 최신 테스트 결과를 모아 집계 xlsx 생성 후 다운로드
- 개별 raw / summary는 task 상태가 `DONE`일 때만 다운로드 허용
- 집계 결과서는 현재 로그인 사용자 기준 최신 `TEST/RETEST` 결과만 포함한다
- raw txt 다운로드 파일명은 실제 저장된 `{line_name}-{timestamp}.txt`를 그대로 사용한다
- 집계 결과서 다운로드 파일명은 실제 저장된 `{business_unit}-{timestamp}.xlsx`를 그대로 사용한다

### 13.6 관리자 SSH 제한 조회 API
- `GET /api/admin/hosts/ssh-limits`
- `POST /api/admin/hosts/{name}/ssh-limits/probe`

정책:
- 목록 조회는 저장된 `ssh_parallel_limit` 캐시만 반환한다
- `probe` 호출 시에만 실제 host에 접속해 재감지한다
- 감지 실패 시 기본값 `10`을 사용하고 관리자 알람 로그에 남긴다

## 14. ezDFS API

### 14.1 조회 API
- `GET /api/ezdfs/modules`
- `GET /api/ezdfs/rules?module_name={value}`

### 14.2 세션 API
- `GET /api/ezdfs/session`
- `PUT /api/ezdfs/session`
- `DELETE /api/ezdfs/session`

`PUT /api/ezdfs/session` payload 예시:
```json
{
  "selected_module": "EZDFS_A",
  "selected_rule": "RULE_01",
  "active_task_id": "task-1001"
}
```

### 14.3 실행 제어 API
- `POST /api/ezdfs/actions/test`
- `POST /api/ezdfs/actions/retest`

### 14.4 상태 API
- `GET /api/ezdfs/status`
- `GET /api/ezdfs/status/{task_id}`

### 14.5 결과 API
- `GET /api/ezdfs/results/{task_id}/raw`
- `POST /api/ezdfs/results/{task_id}/summary`
- `GET /api/ezdfs/results/{task_id}/summary`

정책:
- RTD와 동일한 mock 정책 적용

## 15. My Page API
- `GET /api/mypage/rtd/recent`
- `GET /api/mypage/ezdfs/recent`

정책:
- 현재 로그인 사용자 기준 최근 이력 반환

## 16. 스키마 정책

현재 관리자 설정 스키마는 아래 원칙을 따른다.
- `Create` request는 사용자가 입력하는 필드만 가진다
- `Update` request는 수정 가능한 필드만 가진다
- `Response`에는 `modifier`, `created_at`, `updated_at`를 포함한다

예시:
- `UserUpdateRequest`
- `HostConfigCreate`, `HostConfigUpdate`, `HostConfigResponse`
- `RtdConfigCreate`, `RtdConfigUpdate`, `RtdConfigResponse`
- `EzdfsConfigCreate`, `EzdfsConfigUpdate`, `EzdfsConfigResponse`

## 17. 운영 / 마이그레이션 정책

### 17.1 초기화
- 서버 시작 시 DB 테이블을 생성한다
- 환경변수 기준 기본 관리자 계정을 seed할 수 있다

### 17.2 legacy 컬럼 보정
- 기존 SQLite 파일과의 호환을 위해 서버 시작 시 legacy 컬럼 보정 로직을 수행한다
- 현재 보정 대상
  - `host_configs.modifier`
  - `rtd_configs.modifier`
  - `ezdfs_configs.modifier`

정책:
- 컬럼이 없으면 `ALTER TABLE ... ADD COLUMN modifier ...`로 자동 추가한다
- 기존 데이터 호환성을 유지하는 것이 우선이다

## 18. 구현 우선순위
1. 인증 / 관리자 CRUD / 세션 API 안정화
2. RTD SSH 조회 / 실행 / 결과 파일 흐름 안정화
3. 집계 결과서 포맷과 오프라인 환경 커스텀 포인트 정리
4. ezDFS 및 나머지 mock 기능의 실제 외부 연동 교체
