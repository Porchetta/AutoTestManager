# AutoTestManager

RTD 및 ezDFS 테스트 흐름을 웹에서 관리하기 위한 `Vue 3 + FastAPI` 기반 테스트 매니저입니다.

현재 기준 구현은 아래 방향에 맞춰져 있습니다.
- 로그인 / 관리자 권한 기반 웹 사용
- Admin에서 Host / RTD / ezDFS 설정 관리
- RTD Test Manager 기반 단계형 실행 제어
- 사용자별 세션 복원
- 결과 파일 다운로드 및 집계 결과서 생성
- 오프라인 환경을 고려한 커스텀 포인트 분리

## 현재 상태 요약

- RTD
  - Rule / Version 조회는 개발 라인 기준 SSH로 동작
  - Macro 확인은 사용자가 `탐색` 버튼을 눌렀을 때만 `.rule` / macro 파일을 읽어 비교
  - 복사 / 컴파일 / 테스트는 커스텀 가능한 실행 훅을 통해 수행
  - 타겟 라인별 상태 모니터와 Raw Data 다운로드 제공
  - Step 6 `Execute all`로 `복사 -> 컴파일 -> 테스트 -> 결과서 생성`을 순차 실행 가능
  - 테스트 결과서 생성 시 선택된 라인의 최신 테스트 결과를 모아 `.xlsx`로 다운로드
  - 개발 라인 자체는 복사 대상에서 제외
- ezDFS
  - 현재는 mock 또는 단순 생성 로직 중심
  - test / retest / raw / summary 흐름은 유지하되, 추후 실제 외부 연동으로 교체 가능

## 프로젝트 구성

- `frontend/`
  - Vue 3 + Vite + Pinia 기반 SPA
- `backend/`
  - FastAPI + SQLAlchemy + SQLite 기반 API 서버
- `docs/Front.md`
  - 현재 프론트 구현 기준 문서
- `docs/Back.md`
  - 현재 백엔드 구현 기준 문서
- `docs/plan.md`
  - 상위 기획 문서

## 주요 기능

### 인증
- 회원가입
- 로그인 / 로그아웃
- JWT 기반 인증
- 비밀번호 변경

### Admin
- User Management
  - 모듈 필터
  - 사용자 모듈 / 승인 여부 / 관리자 여부 인라인 수정
  - 사용자 삭제
- Host Settings
  - Host 등록 / 수정 / 삭제
  - SSH 병렬 제한값 감지 / 재감지
- RTD Settings
  - 사업부 필터
  - RTD config 등록 / 수정 / 삭제
- ezDFS Settings
  - ezDFS config 등록 / 수정 / 삭제

공통 정책:
- 모든 삭제는 커스텀 확인 모달 사용
- `modifier`는 로그인한 관리자 이름으로 자동 기록
- Host의 SSH 병렬 제한 감지 실패 시 기본값 `10`을 사용하고 관리자 알람 로그에 남김

### RTD Test Manager
- 6단계 Manager 구조
  - 사업부 선택
  - 개발 라인 선택
  - Rule 선택
  - Macro 확인
  - 타겟 라인 선택
  - 실행 제어
- Rule / Version catalog는 개발 서버 SSH 조회 기반
- 선택한 Rule target 조합을 누적 관리
- old/new `.rule` 파일 비교 후 Macro 차이 확인
- Macro는 Step 4에서 수동 `탐색` 시에만 조회
- 탐색된 Old / New Macro는 기본 전체선택 상태로 시작하며, 개별 체크 또는 `전체선택 / 전체 해제` 가능
- 타겟 라인도 `전체 선택 / 전체 해제` 가능
- 상단 실행 제어
  - `복사`
  - `컴파일`
  - `테스트`
  - `테스트 결과서 생성`
  - `Execute all`
- `Execute all`은 위 4개 과정을 순서대로 끝까지 실행하며, 중간 실패 시 다음 단계로 넘어가지 않음
- 하단 `Target Status Monitor`
  - 라인별 상태 chip
  - 개별 `복사 / 컴파일 / 테스트`
  - `Raw Data` 다운로드
  - compact monitor tile 레이아웃 사용
- 실행 제어 패널에서는 `초기화`로 세션과 선택 상태를 모두 비우고 Step 1로 복귀 가능
- 세션 저장 / 복원

### ezDFS Test
- 3단계 플로우
- module / rule 선택
- test / retest 실행
- task 상태 polling
- RawData 다운로드
- 결과서 생성 / 다운로드
- 세션 저장 / 복원

### My Page
- 비밀번호 변경
- 최근 RTD / ezDFS 결과 조회

## RTD 커스텀 포인트

오프라인 환경 커스텀은 아래 파일을 기준으로 진행하면 됩니다.

- `backend/app/services/rtd_catalog_custom.py`
  - Rule source file 목록 조회
  - 파일명 파싱으로 `rule_name`, `version` 생성
  - `.rule` 파일 텍스트 읽기
  - Rule 텍스트에서 Macro list 추출
  - nested macro 재귀 탐색
- `backend/app/services/rtd_execution_custom.py`
  - 복사
  - 컴파일
  - 테스트 / 재테스트
- `backend/app/services/rtd_report_custom.py`
  - 라인별 테스트 결과를 모아 집계 결과서 생성

기본 구현은 다음을 전제로 합니다.
- Rule 파일은 개발 라인 `home_dir_path`
- Macro 파일은 개발 라인 기준 `../Macro`
- 원격 명령은 `bash --noprofile --norc -lc ...` 형식으로 실행
- compile 명령: `./atm_compiler {rule_name} {line_name}`
- test 명령: `./atm_testscript {rule_name} {line_name}`

## 기술 스택

### Frontend
- Vue 3
- Vite
- Pinia
- Vue Router
- Axios

### Backend
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT
- Paramiko

## 개발 환경

현재 개발 기준 환경은 `Windows + WSL` 입니다.

### Backend 실행

```bash
cd /home/hyun/develope/AutoTestManager/backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh
./run-dev.sh
```

기본 URL:
- API: `http://127.0.0.1:10223`
- Swagger Docs: `http://127.0.0.1:10223/docs`
- Health: `http://127.0.0.1:10223/health`

기본 관리자 계정:
- `user_id`: `admin`
- `password`: `admin1234`

### Frontend 실행

```bash
cd /home/hyun/develope/AutoTestManager/frontend
cp .env.example .env
npm install
npm run dev
```

기본 URL:
- Frontend: `http://127.0.0.1:4203`

기본 환경 변수:
- `VITE_API_BASE_URL=http://127.0.0.1:10223`

## 데이터 / 파일 저장

- SQLite DB: `backend/data/autotestmanager.db`
- 결과 파일 루트: `backend/data/results/`

주요 저장 규칙:
- RTD Raw Data
  - `backend/data/results/rtd/raw/{user_id}/{line_name}-{timestamp}.txt`
- RTD 개별 task summary
  - `backend/data/results/rtd/{task_id}/rtd_{task_id}_summary.xlsx`
- RTD 집계 결과서
  - `backend/data/results/rtd/reports/{user_id}/{business_unit}-{timestamp}.xlsx`

정책:
- DB에는 결과 본문이 아니라 파일 경로를 저장
- 다운로드 파일명은 실제 저장된 파일명을 그대로 사용
- monitor의 Raw Data 다운로드는 현재 로그인 사용자 기준 가장 최근 `TEST/RETEST` 결과가 raw를 만든 경우에만 활성화
- SSH 병렬 제한 감지 실패 알람 로그: `backend/data/logs/admin_alert.log`

## 현재 구현 정책

- RTD는 SSH 기반 조회 / 실행 구조를 갖추고 있으며, 오프라인 환경에 맞게 커스텀 가능
- ezDFS는 현재 mock 또는 단순 생성 로직을 유지
- 최종 운영 포맷의 결과서 레이아웃은 아직 확정 전
- 리포트 엔진 연동은 현재 포함하지 않음

## 문서 참조

- 프론트 상세 기준: [docs/Front.md](/home/hyun/develope/AutoTestManager/docs/Front.md)
- 백엔드 상세 기준: [docs/Back.md](/home/hyun/develope/AutoTestManager/docs/Back.md)

## 참고

- 백엔드 시작 시 기본 관리자 seed와 legacy `modifier` 컬럼 보정이 수행될 수 있습니다.
- Admin 설정의 `Host / RTD / ezDFS`는 모두 수정 가능하며, 수정 시 `modifier`가 자동 갱신됩니다.
- Host Settings에서 `SSH Limit` 컬럼과 `감지` 버튼으로 현재 병렬 제한 캐시를 확인할 수 있습니다.
- RTD 실행 제어와 결과서 생성 정책은 `docs/Back.md`를 우선 기준으로 봐주세요.
