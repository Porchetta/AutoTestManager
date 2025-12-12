# MSS Test Manager DB 명세서 (MySQL)

## 💻 환경 및 구성

| 구분 | 내용 |
| :--- | :--- |
| **DB 엔진** | MySQL 8 (Docker Compose에서 `mysql:8.0` 사용) |
| **초기화 스크립트** | `database/init.sql`을 `/docker-entrypoint-initdb.d/`로 마운트하여 테이블 및 기본 Admin 계정 생성 + 테스트 호스트 설정 |
| **기본 접속 정보** | DB: `mss_test_manager`, User: `mss_user` / `mss_password` (루트 비밀번호 `rootpassword`) |
| **포트/볼륨** | 3306 노출, `db_data` 볼륨으로 데이터 영속화 |
| **네트워크** | `mss_network` 브리지 네트워크를 통해 백엔드 컨테이너와 통신 |

---

## 🏛️ 테이블 스키마

### 1. `users`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `user_id` | VARCHAR(50) | PK | 사용자 ID |
| `password_hash` | VARCHAR(255) | NOT NULL | bcrypt 해시 비밀번호 |
| `user_name` | VARCHAR(50) | NOT NULL | 사용자 이름 |
| `module_name` | VARCHAR(50) | NOT NULL | 소속/모듈명 저장 |
| `is_admin` | BOOLEAN | NOT NULL DEFAULT FALSE | 관리자 여부 |
| `is_approved` | BOOLEAN | NOT NULL DEFAULT FALSE | 승인 여부 |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |

> init.sql에서 `admin` 계정이 기본 삽입(승인/관리자 true, 사전 해시 비밀번호).

### 2. `host_config`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `name` | VARCHAR(100) | PK | 개발 서버 이름(고유) |
| `ip` | VARCHAR(100) | NOT NULL | 개발 서버 IP |
| `user_id` | VARCHAR(100) | NOT NULL | 접속 계정 ID |
| `password` | VARCHAR(255) | NOT NULL | 접속 계정 비밀번호 |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |

### 3. `rtd_config`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `line_name` | VARCHAR(50) | PK | 라인 이름(고유) |
| `line_id` | VARCHAR(50) | NOT NULL | 라인 ID |
| `business_unit` | VARCHAR(50) | NOT NULL | 사업부 이름 |
| `home_dir_path` | VARCHAR(255) | NOT NULL | Rule 탐색용 홈 디렉터리 |
| `host` | VARCHAR(100) | FK → `host_config.name` (ON DELETE RESTRICT) | 테스트 대상 개발 서버 |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |
| `modifier` | VARCHAR(50) | NULL | 수정자 기록 |

### 4. `ezdfs_config`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `module_name` | VARCHAR(50) | PK | 대상 모듈/서버 이름 |
| `port_num` | VARCHAR(50) | NOT NULL | 대상 포트 |
| `home_dir_path` | VARCHAR(255) | NOT NULL | Rule 디렉터리 경로 |
| `host` | VARCHAR(100) | FK → `host_config.name` (ON DELETE RESTRICT) | 테스트 대상 개발 서버 |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |
| `modifier` | VARCHAR(50) | NULL | 수정자 |

### 5. `user_rtd_favorites`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | INT | PK, AUTO_INCREMENT | 고유 ID |
| `user_id` | VARCHAR(50) | FK → `users.user_id` (ON DELETE CASCADE) | 사용자 ID |
| `line_name` | VARCHAR(50) | FK → `rtd_config.line_name` (ON DELETE SET NULL) | 관련 라인 |
| `rule_name` | VARCHAR(50) | NOT NULL | 즐겨찾기 Rule |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |

### 6. `user_ezfds_favorites`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | INT | PK, AUTO_INCREMENT | 고유 ID |
| `user_id` | VARCHAR(50) | FK → `users.user_id` (ON DELETE CASCADE) | 사용자 ID |
| `module_name` | VARCHAR(50) | FK → `ezdfs_config.module_name` (ON DELETE SET NULL) | 모듈명 |
| `rule_name` | VARCHAR(50) | NOT NULL | 즐겨찾기 Rule |
| `created` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 생성 시각 |

### 7. `test_results`

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `task_id` | VARCHAR(100) | PK | 비동기 작업 ID |
| `user_id` | VARCHAR(50) | FK → `users.user_id` (ON DELETE CASCADE) | 요청 사용자 |
| `test_type` | VARCHAR(10) | NOT NULL | `RTD` 또는 `EZDFS` 구분 |
| `raw_result_path` | VARCHAR(255) | NULL | Raw 데이터 경로 |
| `summary_result_path` | VARCHAR(255) | NULL | 종합 결과 경로 |
| `status` | VARCHAR(20) | NOT NULL | `PENDING`/`RUNNING`/`SUCCESS`/`FAILED` |
| `request_time` | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 요청 시각 |
| `rtd_old_version` | VARCHAR(50) | NULL | RTD만: Old 버전 |
| `rtd_new_version` | VARCHAR(50) | NULL | RTD만: New 버전 |

> RTD Rule/Macro 목록 및 버전 정보는 파일 시스템/외부 연동으로 조회하며 별도 테이블을 두지 않는다. 컴파일/테스트 상태는 프론트/백엔드 세션 메모리에 유지되고, 완료된 테스트만 `test_results`에 기록된다.
