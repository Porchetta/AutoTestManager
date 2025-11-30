# MSS Test Manager DB 서버 명세서 (MySQL 기준)

## 💻 DB 환경 및 기술 스택

| 구분 | 내용 | 비고 |
| :--- | :--- | :--- |
| **DB 시스템** | Oracle XE 또는 **MySQL** | 초기화(Init) 스크립트 작성 필요 |
| **운영 환경** | Linux Docker 컨테이너 | 데이터 영속성을 위해 **Volume Mount** 필수 |
| **네트워크** | 외부 인터넷 연결이 되지 않는 사내망 사용 | Back End 컨테이너와 내부 네트워크 연결 필요 |

---

## 🏛️ 주요 테이블 스키마 명세

### 1. 🧑‍💻 사용자 및 권한 관리 테이블 (`users`)

| 컬럼 명 | 데이터 타입 (MySQL 기준) | Null 허용 | 설명 |
| :--- | :--- | :--- | :--- |
| `user_id` | `VARCHAR(50)` | NO | 사용자 ID (Primary Key) |
| `password_hash` | `VARCHAR(255)` | NO | 비밀번호 해시 값 (보안 필수) |
| `is_admin` | `BOOLEAN` | NO | Admin 권한 여부 (`True`/`False`) |
| `is_approved` | `BOOLEAN` | NO | 가입 승인 여부 (Admin 메뉴에서 관리) |
| `created_at` | `DATETIME` | NO | 사용자 생성 시각 |

### 2. 📝 RTD 환경 설정 테이블 (`rtd_config`)

| 컬럼 명 | 데이터 타입 (MySQL 기준) | Null 허용 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | NO | 자동 증가 Primary Key |
| `business_unit` | `VARCHAR(100)` | NO | 사업부 명 |
| `development_line` | `VARCHAR(100)` | NO | 개발 라인 명 (사업부에 종속) |
| `home_dir_path` | `VARCHAR(255)` | NO | 해당 라인의 Home Directory 경로 |
| `is_target_line` | `BOOLEAN` | NO | 이 라인이 Test 대상 타겟 라인으로 사용 가능한지 여부 |

### 3. 🎯 ezDFS 환경 설정 테이블 (`ezdfs_config`)

| 컬럼 명 | 데이터 타입 (MySQL 기준) | Null 허용 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | NO | 자동 증가 Primary Key |
| `target_server_name` | `VARCHAR(100)` | NO | 타겟 서버 명 |
| `dir_path` | `VARCHAR(255)` | NO | 서버 내 Rule Directory 경로 |

### 4. ⭐ 사용자 즐겨찾기 테이블 (`user_favorites`)

| 컬럼 명 | 데이터 타입 (MySQL 기준) | Null 허용 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | NO | 자동 증가 Primary Key |
| `user_id` | `VARCHAR(50)` | NO | 사용자 ID (Foreign Key to `users`) |
| `rule_name` | `VARCHAR(100)` | NO | 즐겨찾는 Rule 이름 |
| `target_server_id` | `INT` | YES | 관련 타겟 서버 ID (Foreign Key to `ezdfs_config`) |

### 5. 📜 테스트 결과 추적 테이블 (`test_results`)

| 컬럼 명 | 데이터 타입 (MySQL 기준) | Null 허용 | 설명 |
| :--- | :--- | :--- | :--- |
| `task_id` | `VARCHAR(100)` | NO | 비동기 작업 Task ID (Primary Key) |
| `user_id` | `VARCHAR(50)` | NO | 요청 사용자 ID (Foreign Key to `users`) |
| `test_type` | `VARCHAR(10)` | NO | 테스트 종류 (`RTD` 또는 `EZDFS`) |
| `raw_result_path` | `VARCHAR(255)` | YES | Raw Data 파일 저장 경로 |
| `summary_result_path` | `VARCHAR(255)` | YES | 종합 결과 파일 저장 경로 |
| `status` | `VARCHAR(20)` | NO | 작업 상태 (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`) |
| `request_time` | `DATETIME` | NO | 테스트 요청 시각 |
| `rtd_old_version` | `VARCHAR(50)` | YES | RTD Only: Old Rule 버전 정보 |
| `rtd_new_version` | `VARCHAR(50)` | YES | RTD Only: New Rule 버전 정보 |