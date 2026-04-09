# AutoTestManager Backend Reference

## 1. 문서 목적
이 문서는 `docs/plan.md`, `docs/Front.md`를 기준으로 현재 구현된 AutoTestManager 백엔드의 기준 동작을 정리한 문서다.

목표는 다음 3가지를 명확히 하는 것이다.
- 백엔드가 반드시 구현해야 하는 기능 범위
- 프론트엔드와 맞춰야 하는 실제 API 계약
- 지금은 `mock`으로 두고 이후 커스텀 구현으로 교체할 기능 범위

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
- mock 기반 다운로드 / 결과서 생성 기능

### 4.2 이번 구현에서 mock 처리할 기능
아래 4개 기능은 실제 외부 시스템 연동 없이 반드시 `mock`으로 구현한다.
- 테스트 요청
- 테스트 결과서 생성
- RawData 다운로드(`.txt`)
- 테스트 결과서 다운로드(`.xlsx`)

### 4.3 이번 구현에서 하지 않는 것
- 실제 RTD 서버 접속 및 파일 복사
- 실제 컴파일 실행
- 실제 외부 테스트 툴 호출
- 실제 리포트 생성 엔진 연동
- 실제 raw data 수집 로직

즉, 현재 단계에서는 "동작하는 백엔드 인터페이스 + 상태 흐름 + mock 산출물 생성"이 목표다.

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
- 요청 시 `task_id`를 반환하고 실제 상태는 background task가 갱신한다
- 현재 단계에서는 mock background task로 상태 전이를 흉내 낸다

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
- `created_at`
- `updated_at`

정책:
- `name`은 unique
- `modifier`는 수동 입력을 받지 않고 로그인한 관리자 `user_name`을 자동 저장한다

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

## 10. mock 정책

### 10.1 mock 대상 기능
아래 기능은 실제 연동 없이 mock으로 구현한다.
- 테스트 요청
- 결과서 생성 요청
- RawData 다운로드
- 결과서 다운로드

### 10.2 mock 동작 원칙
- API 계약은 실제 운영 버전과 동일하게 유지한다
- 내부 구현만 mock으로 둔다
- mock task는 일정 시간 후 상태가 `DONE` 또는 `FAIL`이 되도록 만든다
- 기본값은 성공(`DONE`)으로 한다

### 10.3 mock 파일 규칙
- RawData 파일은 `.txt`
- 결과서 파일은 `.xlsx`
- 요청 시 실제 파일을 생성해 다운로드 가능하게 한다

권장 경로:
- `/data/results/rtd/{task_id}/raw.txt`
- `/data/results/rtd/{task_id}/summary.xlsx`
- `/data/results/ezdfs/{task_id}/raw.txt`
- `/data/results/ezdfs/{task_id}/summary.xlsx`

### 10.4 mock 파일 내용
- RawData txt
  - `task_id`
  - `test_type`
  - `target_name`
  - `requested_at`
  - `status`
  - dummy log lines
- Summary xlsx
  - Sheet 1: `summary`
  - 컬럼 예시: `task_id`, `test_type`, `target_name`, `status`, `requested_at`, `ended_at`, `message`

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
- `GET /api/rtd/versions/macros?macro_name={value}`
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

### 13.1.1 Macro 비교 정책
- `POST /api/rtd/macros/compare`는 Step 3에서 선택한 Rule target 목록을 받아 old/new rule 파일을 비교한다
- 각 Rule target에 대해 세션 cache에서 `rule_name + version`으로 원본 `file_name`을 찾는다
- 해당 파일을 SSH로 읽어 `.rule` 파일 내용을 가져온다
- macro list는 파일 내용을 줄 단위로 파싱해서 생성한다
- 빈 줄은 제외한다
- `//`, `#`, `;`로 시작하는 주석 줄은 제외한다
- 줄 끝 주석 제거 후 남은 텍스트를 macro 항목으로 사용한다
- old file과 new file 내용이 다른 경우에만 old/new macro 차이를 계산한다
- 응답 예시:
```json
{
  "success": true,
  "data": {
    "old_macros": ["MACRO_A", "MACRO_B"],
    "new_macros": ["MACRO_C"],
    "has_diff": true
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
    "old_macros": ["MACRO_A"],
    "new_macros": ["MACRO_B"],
    "has_diff": true
  },
  "target_lines": ["LINE_B", "LINE_C"],
  "active_task_ids": ["task-001", "task-002"]
}
```

정책:
- `catalog_cache`는 Rule / Version SSH 조회 결과를 담는 내부 세션 데이터다
- 일반 세션 저장 시 같은 `selected_line_name`이면 기존 `catalog_cache`를 유지한다

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
- 현재는 실제 실행이 아니라 mock task 생성
- 동일 사용자 + 동일 target + 실행중 상태면 `409 Conflict`

### 13.4 상태 API
- `GET /api/rtd/status`
- `GET /api/rtd/status/{task_id}`

### 13.5 결과 API
- `GET /api/rtd/results/{task_id}/raw`
- `POST /api/rtd/results/{task_id}/summary`
- `GET /api/rtd/results/{task_id}/summary`

정책:
- `GET /raw`: mock txt 다운로드
- `POST /summary`: mock xlsx 생성
- `GET /summary`: 생성된 xlsx 다운로드
- task 상태가 `DONE`일 때만 다운로드 허용

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
2. RTD / ezDFS mock task 흐름 안정화
3. 다운로드 / 결과서 생성 mock 품질 보정
4. 이후 실제 외부 연동으로 교체
