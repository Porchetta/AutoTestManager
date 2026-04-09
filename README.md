# AutoTestManager

RTD 및 ezDFS 테스트 흐름을 웹에서 관리하기 위한 Vue + FastAPI 기반 테스트 매니저입니다.

현재 버전은 다음에 집중합니다.
- 로그인 / 관리자 권한 기반 웹 사용
- RTD / ezDFS 테스트 흐름 관리
- Admin 설정 관리
- 세션 복원
- mock 기반 테스트 실행 / RawData 다운로드 / 결과서 생성 / 결과서 다운로드

실제 외부 시스템 연동은 아직 포함하지 않으며, 테스트 실행과 산출물 생성은 현재 `mock` 구현입니다.

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
- RTD Settings
  - 사업부 필터
  - RTD config 등록 / 수정 / 삭제
- ezDFS Settings
  - ezDFS config 등록 / 수정 / 삭제

공통 정책:
- 모든 삭제는 커스텀 확인 모달 사용
- `modifier`는 로그인한 관리자 이름으로 자동 기록

### RTD Test
- 7단계 wizard
- 사업부 / 라인 / Rule / Macro / 버전 / 타겟 라인 선택
- copy / compile / test / retest 실행
- task 상태 polling
- RawData 다운로드
- 결과서 생성 / 다운로드
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

## 개발 환경

현재 개발 기준 환경은 Windows + WSL 입니다.

### Backend 실행
```bash
cd /home/hyun/develope/AutoTestManager/backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh
./run-dev.sh
```

기본 URL:
- API: `http://127.0.0.1:8000`
- Swagger Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

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
- Frontend: `http://127.0.0.1:5173`

기본 환경 변수:
- `VITE_API_BASE_URL=http://127.0.0.1:8000`

## 데이터 / 파일 저장
- SQLite DB: `backend/data/`
- mock 결과 파일: `backend/data/results/`

mock 산출물:
- RawData: `.txt`
- 테스트 결과서: `.xlsx`

## 현재 구현 정책
- RTD / ezDFS 실제 서버 접속은 아직 없음
- 실제 컴파일 / 테스트 툴 호출 없음
- 실제 리포트 엔진 연동 없음
- 대신 API 계약과 화면 흐름은 실제처럼 유지하고, 내부 동작은 mock으로 구성

## 문서 참조
- 프론트 상세 기준: [docs/Front.md](/home/hyun/develope/AutoTestManager/docs/Front.md)
- 백엔드 상세 기준: [docs/Back.md](/home/hyun/develope/AutoTestManager/docs/Back.md)

## 참고
- 백엔드 서버 시작 시 기본 관리자 seed 및 legacy `modifier` 컬럼 보정이 수행될 수 있습니다.
- Admin 설정의 `Host / RTD / ezDFS`는 모두 수정 가능하며, 수정 시 `modifier`가 자동 갱신됩니다.
