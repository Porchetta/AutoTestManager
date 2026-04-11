# AutoTestManager Frontend Specs

## 1. 문서 목적
이 문서는 현재 구현된 AutoTestManager 프론트엔드의 기준 동작을 정리한 문서다.  
`docs/Back.md`와 함께 agent가 프론트 수정 또는 신규 기능 추가 시 직접 참조하는 기준으로 사용한다.

## 2. 기술 스택
- Framework: Vue 3
- Build Tool: Vite
- State Management: Pinia
- Router: Vue Router
- HTTP Client: Axios
- Styling: 라이트 기본 테마 + 다크 토글, 전역 CSS 토큰 기반 디자인 시스템 (`style.css`)
- 폰트: Inter, IBM Plex Sans (Google Fonts)
- Build: Docker image 생성 가능
- Deploy: 오프라인 환경 정적 배포 가능 구조

## 3. 화면 공통 설계

### 3.1 레이아웃
- 전체 화면은 Sidebar + Main Content 구조를 사용한다.
- 로그인 이후 Sidebar는 항상 표시한다.
- Main Content 영역은 라우터 기반으로 페이지를 렌더링한다.
- 엔터프라이즈 신뢰감 톤의 라이트 테마를 기본으로 사용하며, 다크 테마로 전환 가능하다.
- Sidebar는 슬림한 고정 레일 형태를 사용하고, 상단 헤더는 페이지 제목 + 사용자 메타 + 테마 토글 + 로그아웃 아이콘 구조를 사용한다.
- 활성 사이드바 메뉴는 정확한 경로 일치(`router-link-exact-active`) 기준으로 하이라이트된다.

### 3.2 Sidebar 메뉴
- DashBoard
- RTD Test
- ezDFS Test
- Admin
- My Page

정책:
- 로그아웃은 Sidebar 하단이 아니라 우측 상단 헤더 영역의 아이콘 버튼으로 제공한다.

### 3.3 공통 UX 원칙
- 기본 테마는 라이트 테마이며, 우측 상단 헤더의 토글 버튼으로 다크 테마로 전환할 수 있다.
- 테마 설정은 `localStorage`(`atm-theme`)에 저장되어 새로고침 후에도 유지된다.
- 주요 액션은 로딩 상태를 표시한다.
- API 실패 시 전역 Toast 메시지로 사용자에게 안내한다.
- 삭제 같은 중요 액션은 브라우저 기본 `confirm` 대신 커스텀 확인 모달을 사용한다.
- 인증 만료 시 저장된 인증 정보를 제거하고 `/login`으로 이동한다.
- 진행 중 작업이 있는 화면은 서버 세션 기준으로 복원한다.

### 3.4 디자인 시스템
- CSS 토큰은 `:root`(라이트)와 `[data-theme="dark"]` 오버라이드로 이중 구성한다.
- 컬러: teal(`--accent`) 계열을 주요 액센트로 사용하며, success/warning/danger/info 시맨틱 컬러를 분리한다.
- 버튼 종류: `button-primary`(solid teal), `button-secondary`(solid blue), `button-ghost`(중립), `button-danger`(적색 경계)
- 선택 상태 UI: 버튼/카드의 선택 상태는 `data-selected="true"` 또는 `:has(input:checked)`로 제어한다.
- 상태 배지: `.status-badge[data-status]`로 RUNNING/SUCCESS/FAILED/WARNING 등 상태를 시각화한다.
- 공통 클래스:
  - `.choice-grid-inline`: 선택 버튼을 내용 너비 기준으로 flex wrap 나열
  - `.check-grid` + `.choice-grid-inline`: 체크카드도 동일 레이아웃 공유
  - `.manager-section-title-inline`: 제목 h4와 pill/버튼을 가로로 정렬

## 4. 라우팅 구조
- `/login`
- `/signup`
- `/`
- `/rtd`
- `/ezdfs`
- `/admin`
- `/mypage`

### 4.1 라우팅 정책
- 로그인, 회원가입을 제외한 모든 경로는 인증 필요
- JWT가 없거나 만료된 경우 `/login`으로 이동
- `Admin` 메뉴는 관리자 권한 사용자만 접근 가능

## 5. 인증 및 상태 관리

### 5.1 인증 처리
- 로그인 성공 시 access token과 사용자 정보를 `localStorage`에 저장한다.
- 저장 key는 `atm-auth`를 사용한다.
- 앱 시작 시 `localStorage`에서 토큰과 사용자 정보를 복원한다.
- Axios 요청 인터셉터에서 JWT를 자동 첨부한다.
- 401 응답 수신 시 토큰을 제거하고 로그인 화면으로 이동한다.

### 5.2 Pinia Store 구성
- `authStore`
  - token
  - user
  - isAdmin
  - isAuthenticated
- `uiStore`
  - globalLoading
  - globalError
  - globalNotice
  - confirmDialogState
- `rtdStore`
  - RTD Test Manager 상태
  - 세션 저장 / 복원 상태
  - task 상태 목록
  - target monitor 상태
- `ezdfsStore`
  - ezDFS 선택 상태
  - 세션 저장 / 복원 상태
  - task 상태 목록

## 6. 페이지별 상세 스펙

### 6.1 로그인 화면
- 사용자 ID / 비밀번호 입력 폼 제공
- 로그인 버튼 클릭 시 인증 API 호출
- 실패 시 에러 메시지 출력
- 회원가입 페이지 이동 링크 제공

### 6.2 회원가입 화면
- 사용자 ID
- 사용자 이름
- 비밀번호
- 비밀번호 확인
- 모듈명 입력
- 가입 요청 완료 후 승인 대기 메시지 표시

### 6.3 DashBoard
- 서비스 소개 및 주요 기능 요약 표시
- 최근 RTD / ezDFS 테스트 요약 카드 표시
- 운영 메시지 / 공지 배치 가능 구조 유지
- 상단 `Operations Overview` hero와 별도 `Overview Console` 섹션을 사용한다.
- overview 영역은 RTD / ezDFS / Admin 상태를 한 화면에서 요약하는 운영 콘솔형 레이아웃을 사용한다.

### 6.4 Admin 화면
- 상단 탭 버튼 분리형 레이아웃 사용
- 탭 목록
  - User Management
  - Host Settings
  - RTD Settings
  - ezDFS Settings
- 탭은 상단에 분리된 버튼처럼 보이고, 선택된 탭은 아래 패널과 연결된 형태로 표시한다.
- 모든 삭제 액션은 공통 확인 모달을 사용한다.
- 현재 구현은 좌측 등록 폼 + 우측 데이터 그리드를 공통으로 사용하는 `console grid` 톤을 사용한다.
- 등록 폼은 sticky panel처럼 보이고, 목록은 dense data grid 스타일로 정리한다.

#### 6.4.1 User Management
- 사용자 목록 테이블 표시
- 상단에 모듈 필터 드롭다운 제공
  - `ALL` 포함
- 컬럼
  - `user_id`
  - `user_name`
  - `module_name`
  - `is_approved`
  - `is_admin`
  - `created_at`
  - `actions`
- 동작
  - `module_name`, `is_approved`, `is_admin`는 인라인 수정 가능
  - `module_name`은 텍스트 입력으로 수정
  - `is_approved`, `is_admin`은 `Y / N` 드롭다운으로 수정
  - 변경 사항은 row 우측 `반영` 버튼으로 저장
  - 사용자 삭제 가능
- 비고
  - `Action` 컬럼에 approve/reject 전용 버튼을 두지 않는다.
  - 값 자체 옆의 수정 흐름을 사용한다.

#### 6.4.2 Host Settings
- 좌측 등록 폼 + 우측 목록 테이블 구조
- 등록 폼은 내용물 높이만 차지하며, 목록 row 수에 따라 세로로 늘어나지 않는다.
- 컬럼
  - `name`
  - `ip`
  - `login_user`
  - `login_password`
  - `modifier`
  - `SSH Limit`
  - `created_at`
  - `actions`
- 동작
  - 신규 host 등록
  - row 우측 `수정` 버튼으로 편집 모드 진입
  - 편집 중 `반영`, `취소`, `삭제` 제공
  - 수정 가능 필드
    - `name`
    - `ip`
    - `login_user`
    - `login_password`
  - `modifier`는 읽기 전용
  - `SSH Limit`은 host별 감지된 병렬 제한값을 표시한다
  - `SSH Limit` 옆 `감지` 버튼으로 재감지 가능
  - 정렬 가능 컬럼
    - `name`
    - `ip`
    - `login_user`
    - `modifier`
- 정책
  - `modifier`는 로그인한 관리자 이름으로 자동 반영
  - 삭제 시 참조 중이면 실패 메시지 표시

#### 6.4.3 RTD Settings
- 좌측 등록 폼 + 우측 목록 테이블 구조
- 상단에 사업부 필터 드롭다운 제공
  - `ALL` 포함
- 컬럼
  - `line_name`
  - `line_id`
  - `사업부`
  - `Home Path`
  - `host_name`
  - `modifier`
  - `created_at`
  - `actions`
- 동작
  - 신규 등록
  - row 우측 `수정` 버튼으로 편집 모드 진입
  - 편집 중 `반영`, `취소`, `삭제` 제공
  - 수정 가능 필드
    - `line_name`
    - `line_id`
    - `business_unit`
    - `home_dir_path`
    - `host_name`
  - `modifier`는 읽기 전용
  - 정렬 가능 컬럼
    - `line_name`
    - `line_id`
    - `business_unit`
    - `home_dir_path`
    - `host_name`
    - `modifier`
- 표시 정책
  - `Home Path`가 길면 말줄임(`...`) 처리
  - 전체 값은 hover title로 확인 가능

#### 6.4.4 ezDFS Settings
- 좌측 등록 폼 + 우측 목록 테이블 구조
- 컬럼
  - `module_name`
  - `port`
  - `Home Path`
  - `host_name`
  - `modifier`
  - `created_at`
  - `actions`
- 동작
  - 신규 등록
  - row 우측 `수정` 버튼으로 편집 모드 진입
  - 편집 중 `반영`, `취소`, `삭제` 제공
  - 수정 가능 필드
    - `module_name`
    - `port`
    - `home_dir_path`
    - `host_name`
  - `modifier`는 읽기 전용
  - 정렬 가능 컬럼
    - `module_name`
    - `port`
    - `home_dir_path`
    - `host_name`
    - `modifier`
- 표시 정책
  - 긴 경로는 말줄임(`...`) 처리
  - 전체 값은 hover title로 확인 가능

#### 6.4.5 Admin 공통 UI 규칙
- 필터 드롭다운은 컴팩트한 pill 스타일을 사용한다.
- 정렬 표시는 텍스트 `▲ ▼` 대신 아이콘형 삼각 표시를 사용한다.
- 정렬 상태는 새로고침 시 유지하지 않는다.
- 편집 중인 row는 배경색으로 강조한다.
- `modifier`, `actions` 컬럼은 폭을 안정적으로 유지해 표가 틀어지지 않게 한다.
- 테이블 헤더는 dense console grid 톤으로 고정하고, 액션 버튼은 작은 사각형 컨트롤 스타일을 사용한다.

### 6.5 RTD Test 화면
- 6단계 Manager 형식으로 구현
- 상단 단계 선택 바 + 단일 작업 영역 + 하단 `Target Status Monitor` 구조를 사용한다.
- Step strip은 화면 끝까지 늘어나는 버튼 줄이 아니라, 가운데 정렬된 상단 제어 바 형태를 사용한다.
- 전체 RTD 화면은 compact console density 기준으로 카드와 패널 크기를 조정한다.

#### Step 1. 사업부 선택
- 단일 선택
- 선택 변경 시 이후 스텝 상태 초기화

#### Step 2. 개발 라인 선택
- Step 1의 사업부 기준으로 목록 조회
- 단일 선택
- 개발 라인을 선택하면 백엔드가 해당 라인의 RTD 설정을 기준으로 개발 서버에 SSH 접속해 Rule / Version catalog를 준비한다.

#### Step 3. Rule 선택
- line 기준 Rule 목록 조회
- 단순 체크박스 방식이 아니라 누적 추가 방식으로 동작한다.
- 입력부는 압축된 toolbar 형태로 제공한다.
- 세부 흐름
  - `Rule 선택`
  - `Old version 선택`
  - `New version 선택`
  - `추가`
- 추가된 Rule target 목록은 별도의 selection tray 영역에 표시한다.
- 같은 Rule 조합은 중복 추가하지 않는다.
- Rule / Version 목록을 가져오지 못하면 Rule 드롭다운에 `error`가 표시된다.

#### Step 4. Macro 확인
- Step 3에서 추가된 Rule target들의 old/new rule 파일을 기준으로 macro 차이를 계산한다.
- old rule 파일과 new rule 파일의 내용이 다른 경우에만 macro 차이를 보여준다.
- Step 진입 시 자동 탐색하지 않고, 사용자가 `탐색` 버튼을 눌렀을 때만 조회한다.
- 화면은 `Old Macro`, `New Macro` 2개 영역으로 구성한다.
- `Old / New` 결과는 console card 스타일로 표시한다.
- 각 macro 항목 우측 체크박스로 복사 대상 포함 여부를 선택한다.
- 탐색 완료 후 `Old / New` macro는 기본적으로 모두 선택된 상태로 시작한다.
- 각 카드 헤더에 `전체선택`, `전체 해제` 버튼을 제공한다.
- macro 조회 실패 시 오류 메시지를 표시한다.
- 탐색 중에는 버튼이 `탐색중` 상태와 spinner를 보여준다.

#### Step 5. 타겟 라인 선택
- 다중 선택
- `전체 선택` 버튼으로 한 번에 선택 가능
- `전체 해제` 버튼으로 선택을 모두 지울 수 있다
- 선택된 타겟 라인은 Step 6 monitor 기준이 된다.

#### Step 6. 실행 제어
- 상단 `Process` 패널을 제공한다.
- `Process` 패널 안에는 아래 액션 버튼을 순차 흐름으로 배치한다.
  - `복사`
  - `컴파일`
  - `테스트`
  - `테스트 결과서 생성`
- `Execute all`
- 상단 `복사 / 컴파일 / 테스트`는 현재 선택된 모든 타겟 라인에 대해 한 번에 요청한다.
- `테스트 결과서 생성`은 현재 선택된 타겟 라인들의 최신 테스트 결과를 모아 집계 결과서(`.xlsx`)를 다운로드한다.
- 상단 버튼 순서는 `복사 / 컴파일 / 테스트 / 테스트 결과서 생성`이다.
- `Execute all`은 `복사 -> 컴파일 -> 테스트 -> 테스트 결과서 생성` 순으로 모두 끝날 때까지 순차 진행한다.
- 중간 단계 실패 시 이후 단계는 진행하지 않는다.
- 선택된 개발 라인은 복사 대상에서 제외한다.
- 하단 `Target Status Monitor`는 타겟 라인별 카드형 모니터를 표시한다.
- monitor 카드는 일반 대형 카드보다 더 작은 compact console tile 스타일을 사용한다.
- 넓은 화면에서는 한 줄에 여러 라인 카드가 촘촘하게 배치되도록 monitor 전용 grid를 사용한다.
- 각 카드에는 아래 항목이 표시된다.
  - 라인명
  - 현재 상태 chip
  - `복사`
  - `컴파일`
  - `테스트`
  - `Raw Data`
- 현재 상태 chip은 간단한 운영 상태만 표시한다.
  - `Copying [이름]`
  - `Testing [이름]`
  - `Compiling [이름]`
  - `대기 [이름]`
- 카드 내부 `복사 / 컴파일 / 테스트` 버튼은 해당 라인만 개별 실행한다.
- 개발 라인 카드의 `복사` 버튼은 비활성화한다.
- 카드 내부 `Raw Data` 버튼은 현재 로그인 사용자의 해당 라인 최신 `TEST/RETEST` 이력이 raw data를 만든 경우에만 활성화된다.
- `Raw Data` 버튼은 활성화 시 실제 저장된 파일명으로 `.txt`를 다운로드한다.
- 액션 상태 표현 규칙
  - 성공: 초록색 체크 아이콘
  - 실패: 실패 아이콘
  - 진행중 / 대기중: spinner
- 실패한 경우에만 hover title로 예외 원인을 보여준다.
- polling으로 상태를 주기적으로 갱신한다.
- Step 1에서는 `이전` 버튼을 표시하지 않는다.
- Step 6에서는 `다음` 버튼을 표시하지 않는다.

#### RTD 화면 추가 요구사항
- 스텝 이동 시 현재 상태를 서버 세션에 저장
- 새로고침 시 마지막 상태 복원
- 동일 사용자 + 동일 액션 + 동일 타겟의 중복 요청은 백엔드 정책상 제한될 수 있다
- Raw Data는 결과가 있는 라인만 다운로드 버튼 활성화
- Rule / Version / Macro 확인 결과는 서버 세션 기준으로 복원 가능해야 한다
- `복사` 결과 표시는 현재 페이지 수명 동안만 유지되고, 브라우저 새로고침 후에는 다시 초기화될 수 있다
- `초기화` 버튼을 누르면 세션과 선택 상태를 모두 비우고 Step 1 `사업부 선택`으로 돌아간다

### 6.6 ezDFS Test 화면
- 3단계 플로우로 구현

#### Step 1. 타겟 서버 선택
- ezDFS module 목록 조회
- 단일 선택

#### Step 2. Rule 선택
- 선택한 module 기준 Rule 목록 조회
- 단일 선택

#### Step 3. Test Manage
- 테스트 실행
- 재테스트
- 결과서 생성 / 다운로드
- RawData 다운로드
- polling으로 상태 갱신

### 6.7 My Page 화면

#### 6.7.1 비밀번호 변경
- 현재 비밀번호 입력
- 새 비밀번호 입력
- 새 비밀번호 확인
- 성공 / 실패 메시지 표시

#### 6.7.2 최근 RTD 테스트 결과
- 최근 실행 결과 목록 표시
- 결과 다운로드 버튼 제공

#### 6.7.3 최근 ezDFS 테스트 결과
- 최근 실행 결과 목록 표시
- RTD와 동일한 구조로 제공

## 7. API 연동 원칙
- 모든 API는 `/api` prefix 사용
- Axios 공통 인스턴스 사용
- 인증 토큰 자동 첨부
- 공통 에러 핸들링 적용
- 파일 다운로드는 Blob 응답 처리
- 다운로드 파일명은 서버의 `Content-Disposition`을 우선 사용한다

## 8. 컴포넌트 / UI 구성 기준
- `MainLayout`
- `SidebarNav`
- `ConfirmModal`
- `Toast`
- `Admin Tabs`
- `Step Manager`
- `Operation Console`
- `Target Status Monitor Card`
- `Result Download Panel`

공통 스타일 규칙:
- 다크 테마 유지
- `Premium Console` 스타일 유지
- 컴팩트 필터 드롭다운 사용
- 상단 헤더의 사용자 정보는 pill 대신 부드러운 사각형 badge를 사용한다
- 로그아웃은 우측 상단 헤더의 아이콘 버튼으로 제공한다
- 긴 경로 / 긴 문자열은 필요한 컬럼에서 말줄임 처리
- 편집 가능한 테이블 row는 인라인 입력 컴포넌트 사용

## 9. 프론트엔드 비기능 요구사항
- 데스크톱 해상도 우선 대응
- 최소 1280px 폭 기준의 업무 화면 사용성 확보
- 반복 클릭 및 중복 요청 방지
- polling 해제 누락이 없도록 구현
- 파일 다운로드 실패 시 사용자 안내 필요
- 오프라인 배포 환경에서 정적 리소스 경로 문제 없이 동작해야 함

## 10. 개발 산출물
- Vue 3 SPA 프로젝트
- 공통 레이아웃 및 인증 구조
- RTD Test Manager 화면
- ezDFS Test Manager 화면
- Admin 관리 화면
- My Page 화면
- Docker build 설정
