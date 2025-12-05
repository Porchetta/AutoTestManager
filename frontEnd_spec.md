# MSS Test Manager 프론트엔드 명세서

## 💻 환경 및 기술 스택

| 구분 | 내용 |
| :--- | :--- |
| **프레임워크/빌드** | Vue 3 + Vite, Pinia 상태관리, Vue Router SPA 구성 |
| **HTTP 클라이언트** | Axios (기본 baseURL `/api`) + 인터셉터로 JWT 자동 첨부/401 시 로그인 리다이렉트 |
| **스타일** | 전역 `style.css`에 글래스모피즘 기반 다크 테마 정의, 각 View/컴포넌트에서 scoped 스타일 사용 |
| **런타임/배포** | Node 18로 빌드 후 Nginx(80)로 정적 서빙 (`frontend/Dockerfile` 참고) |
| **라우팅 보호** | 라우트 가드에서 토큰 미보유 시 `/login`으로 이동, 토큰은 `localStorage` 보관 |

---

## 🌐 페이지 구조 및 공통 동작

| 영역 | 경로 | 주요 내용 |
| :--- | :--- | :--- |
| **로그인** | `/login` | 사용자명/비밀번호 입력 후 `/api/auth/login` 응답의 토큰을 Pinia 스토어(`auth`)와 `localStorage`에 저장. 실패 시 에러 메시지 표시. |
| **메인 레이아웃** | `/` 이하 | `Sidebar` 컴포넌트가 고정 네비게이션 제공(대시보드/RTD/ezDFS/My Page/Admin, 로그아웃 버튼). 내부 컨텐츠는 `MainLayout`의 `<router-view>`로 렌더링. |
| **대시보드** | `/` | 단순 환영 문구 제공. |
| **마이페이지** | `/mypage` | 비밀번호 변경(`PUT /api/auth/password`) 및 최근 RTD/ezDFS 작업 조회(`GET /api/mypage/*/last-result`)와 재다운로드 버튼 제공. |
| **Admin** | `/admin` | 탭 UI로 사용자/RTD 설정/ezDFS 설정 관리. 모든 요청은 `/api/admin` 엔드포인트 사용. |

공통 요청은 `frontend/src/api.js`의 Axios 인스턴스를 통해 수행하며, 요청 시 토큰 헤더를 자동 부착하고 401 응답 시 토큰을 삭제 후 로그인 화면으로 이동한다.

---

## 📝 RTD Test 플로우 (`/rtd`)

`RTDTest.vue`는 단계형(UI 스텝퍼) 마법사로 구성되며, 진행 상태를 `/api/rtd/session`에 저장/복원한다.

| 스텝 | 주요 UI/동작 | 연동 API |
| :--- | :--- | :--- |
| **1. 사업부 선택** | 사업부 드롭다운 표시. 선택 시 이후 상태 초기화. | `GET /api/rtd/businesses` |
| **2. 개발 라인 선택** | 선택한 사업부에 대한 라디오 카드 목록(line_name/line_id/home_dir_path). | `GET /api/rtd/lines?business_unit=` |
| **3. Rule 선택** | 라인 기반 Rule 목록과 home_dir_path 표시. | `GET /api/rtd/rules?line_name=` |
| **4. 버전 확인** | Old/New 버전 정보 표시. | `GET /api/rtd/rules/{rule_id}/versions` |
| **5. 타겟 라인 선택/테스트 실행** | 체크박스 및 전체 선택. 이미 실행 중인 라인이 있으면 버튼 비활성. | `GET /api/rtd/target-lines?business_unit=` + `POST /api/rtd/test/start` |
| **6. 진행/결과 다운로드** | 폴링으로 라인별 상태/진행률 표시, Raw 다운로드 버튼 제공. | `GET /api/rtd/test/status/{task_id}`, `GET /api/rtd/test/{task_id}/result/raw` |
| **7. 종합 결과/마이페이지 이동** | 변경점 텍스트 입력 후 요약 생성/다운로드, 마이페이지 이동 또는 세션 초기화. | `POST /api/rtd/test/{task_id}/result/summary`, `DELETE /api/rtd/session` |

- 테스트 실행 중엔 `hasRunningLines` 기준으로 실행 버튼을 잠그며, 단계 이동 시마다 세션을 갱신한다.
- Raw/종합 결과는 alert로 파일 경로를 노출하여 다운로드 트리거 위치를 안내한다.

---

## 🎯 ezDFS Test 플로우 (`/ezdfs`)

`EzDFSTest.vue`는 카드 단위로 여러 타겟을 관리하며, 세션은 `/api/ezdfs/session`에 저장된다.

| 기능 | 주요 UI/동작 | 연동 API |
| :--- | :--- | :--- |
| **타겟 서버/Rule 선택** | 서버 리스트를 셀렉트 박스로 제공, 서버 변경 시 Rule 목록 갱신. 타겟 카드 추가/삭제 가능. | `GET /api/ezdfs/servers`, `GET /api/ezdfs/rules?module_name=` |
| **즐겨찾기** | 사용자 즐겨찾기 목록 표시, 카드에 즐겨찾기 적용/저장 버튼 제공. | `GET /api/ezdfs/favorites`, `PUT /api/ezdfs/favorites` (rule_name/module_name 쿼리 파라미터) |
| **Test 실행** | 하나 이상의 타겟(module_name+rule_name) 선택 시 실행 가능. 진행 중 상태 플래그(`isRunning`)로 버튼 비활성. | `POST /api/ezdfs/test/start` |
| **상태 폴링/완료 표시** | 1초 간격 폴링으로 타겟별 진행률/상태 표시. | `GET /api/ezdfs/test/status/{task_id}` |
| **결과 다운로드/요약** | 타겟별 Raw 다운로드와 요약 생성 버튼 제공. | `GET /api/ezdfs/test/{task_id}/result/raw`, `POST /api/ezdfs/test/{task_id}/result/summary` |

세션 초기화 시 타겟/상태/요약 입력값을 모두 리셋하며, 폴링은 완료 또는 오류 시 중단한다.

---

## 👑 Admin 화면 (`/admin`)

- **User Management**: 전체 사용자 목록 조회, 승인/회수(`PUT /users/{id}/status`), Admin 승격/강등(`PUT /users/{id}/role`) 기능 제공.
- **Hosts**: 개발 서버 접속 정보를 IP/user_id/password로 등록/삭제. 모든 RTD/ezDFS 테스트는 등록된 호스트를 통해 실행되므로 설정 전에 `/api/admin/hosts` 로 호스트를 준비해야 함.
- **RTD Config**: line_name/line_id/business_unit/home_dir_path/host/modifier 입력 후 추가, 항목 삭제 기능. 모든 데이터는 `/api/admin/rtd/configs` 로 CRUD.
- **ezDFS Config**: module_name/port/home_dir_path/host/modifier 입력 후 추가 및 삭제. `/api/admin/ezdfs/configs` 로 CRUD.

---

## 🔒 인증/세션 처리 요약

- 로그인 성공 시 JWT를 저장하고 라우터 가드로 보호된 경로 접근 허용.
- `Sidebar` 로그아웃 버튼 클릭 시 토큰/사용자 정보를 제거하고 로그인 화면으로 이동.
- RTD/ezDFS 진행 상태는 서버 메모리 세션에 저장되지만, 프론트는 변경 시마다 `PUT /session` 으로 동기화하여 새로고침/재접속 시 상태 복원.
