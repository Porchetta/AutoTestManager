# MSS Test Manager 백엔드 서버 명세서 (FastAPI)

## 💻 환경 및 런타임

| 구분 | 내용 |
| :--- | :--- |
| **프레임워크** | FastAPI + Uvicorn ASGI 서버 |
| **의존성** | SQLAlchemy, PyMySQL, python-jose, passlib(bcrypt) |
| **포트** | 40223 (`backend/Dockerfile`에서 uvicorn `--reload` 실행) |
| **DB 연결** | `DATABASE_URL` 환경변수로 MySQL 연결 (기본: `mysql+pymysql://mss_user:mss_password@localhost:3306/mss_test_manager`) |
| **CORS** | `http://localhost`, `http://localhost:5173`, `http://localhost:40203` 허용 |
| **스키마 생성** | 서버 기동 시 `Base.metadata.create_all`로 모델 테이블 자동 생성 + `wait_for_db()`로 연결 대기 |

---

## 🔐 인증/Auth 흐름

- **JWT 발급**: `/api/auth/login`(`POST`, `OAuth2PasswordRequestForm`)에서 사용자 인증 후 `access_token`/`token_type= bearer` 반환.
- **비밀번호 변경**: `/api/auth/password`(`PUT`)에서 기존/새 비밀번호 검증 후 해시 업데이트.
- **회원가입**: `/api/auth/register`(`POST`)로 신규 사용자 생성. 기본값은 `is_admin=False`, `is_approved=False`.
- **토큰 검증**: `Authorization: Bearer <token>` 필요. `get_current_active_user`는 승인 여부 검사, `get_current_admin_user`는 Admin 권한 검사.

---

## 👑 Admin API (모든 엔드포인트 prefix: `/api/admin`, Admin 전용)

| 구분 | 메서드/경로 | 설명 |
| :--- | :--- | :--- |
| 사용자 목록 | `GET /users` | 전체 사용자 조회(skip/limit 파라미터 지원, user_name/module_name 포함). |
| 승인/거부 | `PUT /users/{user_id}/status?is_approved=` | 사용자 승인 상태 토글. |
| Admin 권한 | `PUT /users/{user_id}/role?is_admin=` | 관리자 권한 부여/회수. |
| 사용자 삭제 | `DELETE /users/{user_id}` | 사용자 레코드 삭제. |
| 호스트 조회/생성 | `GET /hosts`, `POST /hosts` | 테스트 대상 개발 서버 name/ip/user_id/password 등록. name은 고유해야 함. |
| 호스트 삭제 | `DELETE /hosts/{name}` | 참조 중(`rtd_config`/`ezdfs_config`)이면 400 반환. |
| RTD 설정 조회/생성 | `GET /rtd/configs`, `POST /rtd/configs` | 사업부/라인 설정 CRUD(추가는 line_name/line_id/business_unit/home_dir_path/host/modifier, host 존재 여부 검증). |
| RTD 설정 삭제 | `DELETE /rtd/configs/{line_name}` | 특정 라인 설정 삭제. |
| ezDFS 설정 조회/생성 | `GET /ezdfs/configs`, `POST /ezdfs/configs` | 타겟 서버 모듈 설정 CRUD(module_name/port_num/home_dir_path/host/modifier, host 존재 여부 검증). |
| ezDFS 설정 삭제 | `DELETE /ezdfs/configs/{module_name}` | 특정 모듈 설정 삭제. |

---

## 📝 RTD Test API (prefix: `/api/rtd`, 승인 사용자만)

- 모든 RTD 테스트는 `rtd_config.host`가 가리키는 개발 서버를 대상으로 실행하도록 설계되어 있으며, 호스트 정보는 `host_config` 테이블에서 관리한다(name을 키로 참조).

- **사업부/라인/Rule/Macro/버전**
  - `GET /businesses`: DB에서 사업부 목록 조회(없으면 Memory/Foundry/NRD 기본값 반환).
  - `GET /lines?business_unit=`: 사업부에 속한 라인(line_name, line_id, home_dir_path).
  - `GET /rules?line_name=`: 선택 라인의 home_dir_path 기반 Rule 목록 반환.
  - `GET /macros?rule_name=`: 선택 Rule에 종속된 Macro 목록 반환.
  - `GET /rules/{rule_name}/versions`, `GET /macros/{macro_name}/versions`: Old/New 버전 정보 반환.

- **테이블/복사·컴파일·테스트 실행** (메모리 상태 + DB `test_results` 동기화)
  - `GET /test/table?line_name=`: 선택한 라인들의 최근 컴파일/테스트 시각과 상태를 조회.
  - `POST /test/copy?line_name=&rule_name=&macro_name=`: 타겟 라인에 Rule/Macro 복사.
  - `POST /test/compile?line_name=&rule_name=&macro_name=`: 타겟 라인을 대상으로 컴파일 요청, 상태를 `DONE`/`FAIL` 등으로 업데이트.
  - `POST /test/start?line_name=&rule_name=`: 타겟 라인을 대상으로 테스트 요청, 라인별 queue에 넣어 상태를 `WAIT`→`TESTING`→`DONE`으로 변경.
  - `GET /test/result/rawdata`: 모든 타겟의 테스트가 `DONE`일 때 rawData.zip 경로 반환.
  - `POST /test/result?contents=`: 결과서 생성 및 다운로드 경로 반환(모든 라인 `DONE` 조건).

- **세션 유지**
  - `GET/PUT/DELETE /session`: 사용자별 진행 단계/선택값과 라인별 compile/test 상태를 서버 메모리에 저장, 새로고침 후 복원 가능하도록 지원.

---

## 🎯 ezDFS Test API (prefix: `/api/ezdfs`, 승인 사용자만)

- ezDFS 테스트 역시 `ezdfs_config.host`에 연결된 개발 서버에서 수행되며, 호스트는 Admin이 사전에 `host_config`에 등록해야 한다(name을 키로 참조).

- **타겟/Rule/즐겨찾기**
  - `GET /servers`: DB의 ezDFS 설정 목록 반환.
  - `GET /rules?module_name=`: 선택 모듈의 home_dir_path 기반 모의 Rule 목록 반환.
  - `GET /favorites`: 사용자 즐겨찾기 Rule 이름 목록 반환.
  - `PUT /favorites?rule_name=&module_name=`: 즐겨찾기 추가(중복 검사 없음).

- **테스트 실행/상태**
  - `POST /test/start`: 타겟 목록(payload.targets)을 받아 task 생성 후 백그라운드에서 각 모듈 병렬 처리.
  - `GET /test/status/{task_id}`: 타겟별 진행률/Raw 경로와 전체 상태 반환.
  - `GET /test/{task_id}/result/raw`(+`module_name` optional): 전체 번들 또는 모듈별 Raw 경로 반환(성공 상태만).
  - `POST /test/{task_id}/result/summary?summary_text=`: 모든 타겟 완료 시 요약 파일 경로 생성.

- **세션 유지**
  - `GET/PUT/DELETE /session`: 현재 타겟/요약 입력값을 메모리에 저장하거나 초기화.

---

## 🧑‍💻 My Page API (prefix: `/api/mypage`, 승인 사용자만)

| 메서드/경로 | 설명 |
| :--- | :--- |
| `GET /rtd/last-result` | 해당 사용자의 가장 최근 RTD `test_results` 레코드 반환(없으면 message). |
| `GET /ezdfs/last-result` | 가장 최근 ezDFS 레코드 반환(없으면 message). |

---

## ⚙️ 기타 구현 디테일

- **모델**: `User`, `HostConfig`, `RTDConfig`, `EzDFSConfig`, `UserRTDFavorite`, `UserEZFDSFavorite`, `TestResults`를 SQLAlchemy 모델로 정의. `User`는 `user_name` 필드를 포함하고, `HostConfig`는 `name`을 기본 키로 하며 IP/계정 정보를 가진다. `RTDConfig`/`EzDFSConfig`는 `host_config.name`을 외래키로 참조하며 호스트 삭제 시 참조가 있으면 차단된다.
- **비즈니스 로직**: 테스트 실행/요약 생성은 실제 외부 실행 대신 `asyncio.sleep`으로 모의 진행률을 갱신하고, Raw/요약 경로를 `/tmp` 하위로 설정한다.
- **세션/작업 상태 저장소**: 프로세스 메모리 딕셔너리(`RTD_TASK_STATE`, `EZDFS_TASK_STATE`, `RTD_SESSIONS`, `EZDFS_SESSIONS`) 사용. 재시작 시 초기화됨.
