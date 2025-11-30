# MSS Test Manager 백엔드 서버 명세서 (FastAPI 기준)

## 💻 백엔드 환경 및 기술 스택

| 구분 | 내용 |
| :--- | :--- |
| **프레임워크** | Python FastAPI Framework 사용 |
| **운영 환경** | Linux에서 Docker 띄워서 운영 |
| **포트** | 40223 |
| **네트워크** | 외부 인터넷 연결이 되지 않는 사내망에서 사용 예정 (정적 build 필수) |
| **특이사항** | 비동기 방식 채택 (Uvicorn) |

---

## 1. 🔑 인증 및 사용자 관리 (Auth & User Management)

| 구분 | 기능 명 | HTTP Method | Endpoint (URL) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **로그인** | 사용자 로그인 | `POST` | `/api/auth/login` | User ID와 Password를 받아 DB에서 인증하고, **JWT 토큰** 발급 |
| **로그아웃** | 사용자 로그아웃 | `POST` | `/api/auth/logout` | 서버 세션 또는 클라이언트의 JWT 만료 처리 |
| **비밀번호 변경** | 사용자 비밀번호 변경 | `PUT` | `/api/auth/password` | 현재 비밀번호 확인 후 새 비밀번호로 변경 (My Page 기능 지원) |

---

## 2. ⚙️ Admin 설정 관리 (Configuration Management)

| 구분 | 기능 명 | HTTP Method | Endpoint (URL) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **사용자 목록 조회** | 미승인 및 전체 사용자 조회 | `GET` | `/api/admin/users` | 가입 요청 승인 대기 중인 사용자 목록 및 전체 사용자 목록 조회 |
| **사용자 가입 승인 처리** | 사용자 승인/거부 | `PUT` | `/api/admin/users/{user_id}/status` | Admin이 특정 사용자의 가입을 승인 또는 거부 처리 |
| **사용자 삭제** | 사용자 계정 삭제 | `DELETE` | `/api/admin/users/{user_id}` | 특정 사용자 계정 삭제 |
| **Admin 권한 부여** | 사용자 권한 변경 | `PUT` | `/api/admin/users/{user_id}/role` | 특정 사용자에게 **Admin 권한** 부여/회수 |
| **RTD 설정 조회** | RTD 사업부/라인/경로 목록 조회 | `GET` | `/api/admin/rtd/configs` | 등록된 RTD 설정 정보 목록 조회 |
| **RTD 설정 관리** | RTD 설정 추가/변경/삭제 | `POST`/`PUT`/`DELETE` | `/api/admin/rtd/configs` | 사업부/라인/Home Dir 경로 추가, 변경, 삭제 |
| **ezDFS 설정 조회** | ezDFS 타겟 서버/경로 목록 조회 | `GET` | `/api/admin/ezdfs/configs` | 등록된 ezDFS 설정 정보 목록 조회 |
| **ezDFS 설정 관리** | ezDFS 설정 추가/변경/삭제 | `POST`/`PUT`/`DELETE` | `/api/admin/ezdfs/configs` | 타겟 서버/Dir 경로 추가, 변경, 삭제 |

---

## 3. 📝 RTD Test 로직 (Real-Time Decision Test)

| 구분 | 기능 명 | HTTP Method | Endpoint (URL) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **사업부 목록 조회** | 사업부 List 제공 (Step 1) | `GET` | `/api/rtd/businesses` | 등록된 사업부 목록 제공 |
| **개발라인 목록 조회** | 개발라인 List 제공 (Step 2) | `GET` | `/api/rtd/lines` | **사업부**에 따른 개발라인 목록 제공 |
| **Test 대상 Rule 목록 조회** | Rule List 제공 (Step 3) | `GET` | `/api/rtd/rules` | **개발라인**에 따른 Test 대상 Rule 목록 제공 |
| **Rule 버전 정보 조회** | Old/New Rule Version 확인 (Step 4) | `GET` | `/api/rtd/rules/{rule_id}/versions` | 선택한 **Rule**의 Old/New Rule 버전 정보 제공 |
| **타겟 라인 목록 조회** | 타겟 라인 List 제공 (Step 5) | `GET` | `/api/rtd/target-lines` | **사업부**에 따른 타겟 라인 목록 제공 |
| **Test.jar 수행 요청 (비동기)** | Test 수행 시작 (Step 5-1) | `POST` | `/api/rtd/test/start` | **비동기 작업 큐**에 Test 실행 요청 및 **Task ID** 반환 |
| **Test 상태 조회** | 진행 중인 Test 상태 확인 | `GET` | `/api/rtd/test/status/{task_id}` | 특정 `task_id`의 진행 상태(Progress) 확인 |
| **라인별 결과 다운로드** | Raw Data 다운로드 (Step 6) | `GET` | `/api/rtd/test/{task_id}/result/raw` | Test 완료 후 **라인별 Raw Data** 파일 다운로드 |
| **종합 결과 생성 요청** | 종합 결과 생성 (Step 6) | `POST` | `/api/rtd/test/{task_id}/result/summary` | **전후 변경점 Text**를 포함하여 **종합 Test 결과** 생성 요청 |
| **종합 결과 다운로드** | 종합 결과 파일 다운로드 | `GET` | `/api/rtd/test/{task_id}/result/summary/file` | 생성된 **종합 Test 결과** 파일 다운로드 |
| **진행 과정 관리** | 사용자 진행 과정 저장/조회/초기화 | `PUT`/`GET`/`DELETE` | `/api/rtd/session` | 사용자별 RTD Test 세션 정보 관리 (자동 저장 및 초기화) |

---

## 4. 📝 ezDFS Test 로직 (ezDFS Test)

| 구분 | 기능 명 | HTTP Method | Endpoint (URL) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **타겟 서버 목록 조회** | 타겟 서버 List 제공 (Step 1) | `GET` | `/api/ezdfs/servers` | 등록된 타겟 서버 목록 제공 |
| **Test할 Rule 목록 조회** | Rule List 제공 (Step 2) | `GET` | `/api/ezdfs/rules` | **타겟 서버** 기준으로 Test 대상 Rule 목록 제공 |
| **즐겨찾는 Rule 관리** | 사용자별 즐겨찾기 Rule | `PUT`/`DELETE`/`GET` | `/api/ezdfs/favorites` | 사용자별 Rule **즐겨찾기 추가/삭제/조회** |
| **Test.jar 수행 요청 (비동기)** | Test 수행 시작 (Step 3) | `POST` | `/api/ezdfs/test/start` | **비동기 작업 큐**에 Test 실행 요청 및 **Task ID** 반환 |
| **Test 상태 조회** | 진행 중인 Test 상태 확인 | `GET` | `/api/ezdfs/test/status/{task_id}` | 특정 `task_id`의 진행 상태(Progress) 확인 |
| **결과 다운로드** | Raw Data 다운로드 (Step 4) | `GET` | `/api/ezdfs/test/{task_id}/result/raw` | Test 완료 후 **Raw Data** 파일 다운로드 |
| **종합 결과 생성 요청** | 종합 결과 생성 (Step 5) | `POST` | `/api/ezdfs/test/{task_id}/result/summary` | **전후 변경점 Text**를 포함하여 **종합 Test 결과** 생성 요청 |
| **종합 결과 다운로드** | 종합 결과 파일 다운로드 | `GET` | `/api/ezdfs/test/{task_id}/result/summary/file` | 생성된 **종합 Test 결과** 파일 다운로드 |
| **진행 과정 관리** | 사용자 진행 과정 저장/조회/초기화 | `PUT`/`GET`/`DELETE` | `/api/ezdfs/session` | 사용자별 ezDFS Test 세션 정보 관리 (자동 저장 및 초기화) |

---

## 5. 🧑‍💻 My Page 및 결과 조회 (Results & Personal)

| 구분 | 기능 명 | HTTP Method | Endpoint (URL) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| **RTD 최종 결과 조회** | 마지막 RTD Test 정보 조회 | `GET` | `/api/mypage/rtd/last-result` | 마지막으로 요청한 RTD Test의 기본 정보 제공 |
| **ezDFS 최종 결과 조회** | 마지막 ezDFS Test 정보 조회 | `GET` | `/api/mypage/ezdfs/last-result` | 마지막으로 요청한 ezDFS Test의 기본 정보 제공 |
| **RTD 결과 다운로드 (재요청)** | 마이페이지 RTD 결과 다운로드 | `GET` | `/api/mypage/rtd/download/{task_id}/raw` | 이전 Task ID를 이용해 Raw Data 다운로드 (종합 결과도 별도 엔드포인트 필요) |