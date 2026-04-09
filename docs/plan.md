목적 : MSS 개발자 Test를 위한 웹 기반 Test Manager 개발
개발 Spec :
 - FrontEnd : Vue 3
 - BackEnd : FastAPI + SQLite
 - Build : [Online] Docker image 생성
 - Deploy : [Offline] Docker image 배포

웹 디자인 포멧
 - Sidebar 기반 메뉴 이동
 - Sidebar Tab
   - DashBoard
   - RTD Test
   - ezDFS Test
   - Admin

기능
1. 공통
 - 로그인 / 로그아웃 / 회원가입
   - JWT 기반 인증 및 보호 라우팅

2. Admin
 - User Management
   - 사용자 목록 조회
   - 사용자 승인 / 반려
   - Admin 권한 부여 / 회수
   - 사용자 삭제
 - Host Settings
   - 테스트용 개발 서버(host) 등록
   - host 목록 조회
   - host 삭제
   - 다른 설정에서 사용 중인 host 삭제 방지
 - RTD Settings
   - RTD line 정보 등록
   - RTD line 목록 조회
   - RTD line 삭제
   - business_unit / host / home_dir_path / modifier 관리
 - ezDFS Settings
   - ezDFS module 정보 등록
   - ezDFS module 목록 조회
   - ezDFS module 삭제
   - port / host / home_dir_path / modifier 관리

3. RTD Test (step by step Process)
 - Step 1. 사업부 선택(business unit) - 단일 선택
 - Step 2. 개발 라인 선택(line_name) - 단일 선택
 - Step 3. Rule 선택(rule_name) - 다중 선택
 - Step 4. Macro 선택(macro_name) - 다중 선택
 - Step 5. Rule / Macro 버전(Old / New) - 각각 단일 선택
 - Step 6. 타겟 라인 선택 - 다중 선택
 - Step 7. Test Manage 화면
   - Target Rule/Macro 복사 버튼
   - Target Rule/Macro 컴파일 버튼
   - 타겟 라인별 테스트 실행 버튼
   - 타겟 라인 별 Process 진행 모니터링 카드
     - 진행 상태 표기, Raw Data 다운로드 버튼, 재테스트 버튼
   - 결과서 생성 버튼 - myPage에서 조회 및 다운로드 가능
    - 결과서 다운로드 버튼
 - 테스트 도중 페이지 새로고침 시 상태 복원

4. ezDFS Test (step by step Process)
 - Step 1. 타겟 서버 선택 (ezDFS module)
 - Step 2. Rule 선택 - 단일 선택
 - Step 3. Test Manager 화면
   - 진행 상태 표기, Raw Data 다운로드 버튼, 재테스트 버튼
   - 결과서 생성 버튼 - myPage에서 조회 및 다운로드 가능
 - 테스트 도중 페이지 새로고침 시 상태 복원

5. My Page
 - 비밀번호 변경
 - 최근 RTD 테스트 결과 조회 및 다운로드
 - 최근 ezDFS 테스트 결과 조회 및 다운로드
