# Custom Function Refactoring Plan

`docs/customFunction.md`에 정의된 신규 함수명에 맞춰 각 `*_custom.py`의
퍼블릭 API를 정리하기 위한 계획서다. 각 custom 파일의 기존 docstring을
기준으로 함수들을 병합·리네이밍하고, 호출측(orchestrator)의 import와
호출 라인도 함께 수정한다.

---

## 0. 변경 원칙

1. **퍼블릭 API 축소**: `customFunction.md`에 명시된 함수만 외부로 노출한다.
   그 외에 현재 public처럼 쓰이던 함수는 모듈 내부 helper로 격하(`_`
   접두어)하거나, orchestrator 내부 helper로 흡수한다.
2. **1-step 호출**: 현재는 `fetch_*_file_names()` → `parse_*_catalog_entries()`
   처럼 catalog 조회가 2-step으로 나뉘어 있다. 신규 `get_rule_file_list()`
   1회 호출로 완결되도록 병합한다.
3. **카탈로그 반환 스키마 동일 유지**: `{"file_name", "rule_name", "version"}`
   dict list. ezDFS의 `old_version`은 orchestrator에서 병합하므로
   catalog 함수는 기존 필드만 반환한다.
4. **helper 유지**: `read_rule_source_text`, `read_rule_source_bytes`,
   `extract_sub_rule_list_from_rule_text`, `resolve_recursive_sub_rule_list`,
   `find_latest_backup_version`은 신규 스펙에는 없지만 orchestrator
   및 `svn_upload_custom.py`에서 실사용 중이므로 모듈 내부 helper로
   그대로 둔다(이름만 언더스코어 붙이지 않고 현 그대로 유지).
5. **RTD execution 이름은 이미 일치**: `execute_copy_action`,
   `execute_compile_action`, `execute_test_action`은 변경 없다.
6. **ezDFS execution 개명**: `execute_ezdfs_test_action` → `execute_test_action`.
   같은 이름을 RTD/ezDFS 양쪽이 공유하므로 caller는 모듈 경로로 구분한다.

---

## 1. RTD Catalog — `rtd_catalog_custom.py`

### 1.1 신규 퍼블릭 함수

#### `get_rule_file_list(host, login_user, home_dir_path) -> list[dict[str, str]]`
현재 `fetch_rule_source_file_names()` + `parse_rule_catalog_entries()`를
하나로 합친 것.

| 항목 | 설명 |
|---|---|
| Input `host` | `HostConfig` — RTD Dispatcher 디렉토리를 가진 원격 host |
| Input `login_user` | `str` — SSH 로그인 계정 |
| Input `home_dir_path` | `str` — Dispatcher 디렉토리 절대경로 |
| Output | `list[dict[str, str]]` — catalog row 리스트 |
| Output row | `{"file_name": <원본 파일명>, "rule_name": <`_PC` 앞 토큰>, "version": <`.report` 제거한 뒷 토큰>}` |
| 정렬 | `rule_name` → `version` (소문자 기준) |

동작:
- `<home_dir_path>` 밑의 `maxdepth-1` 파일명을 SSH로 조회
- `_PC`를 포함하고 `.report`로 끝나는 이름만 통과
- `get_version_from_filename()`으로 version 추출
- 실패 시 `CatalogError` raise

#### `get_macro_file_list(host, login_user, home_dir_path, rule_file_name) -> list[str]`
선택한 rule/report 1건이 참조하는 **전체** Macro report 이름 목록을 반환한다.
기존에는 orchestrator(`catalog_service.get_macro_list_by_rule_name`)가
`read_rule_source_text()` + `extract_macro_list()` 2-step을 실행했으나,
신규에서는 custom 계층에서 1-step으로 처리한다.

| 항목 | 설명 |
|---|---|
| Input `host` | `HostConfig` |
| Input `login_user` | `str` |
| Input `home_dir_path` | `str` — Dispatcher 디렉토리 |
| Input `rule_file_name` | `str` — `get_rule_file_list()` 결과의 `file_name` |
| Output | `list[str]` — 해당 rule이 의존하는 전체 macro `.report` 이름 목록(중복 제거, 등장순) |

동작:
- 원격에서 해당 rule/report 파일 본문을 읽음 (내부적으로 `read_rule_source_text()` 호출)
- 각 line을 trim 한 뒤 `//`, `#`, `;` 주석은 버림
- 중복 제거하고 첫 등장 순서를 보존
- 반환 이름에는 경로·확장자 조작을 하지 않음(기존 `extract_macro_list`와 동일 동작)

**중요 — "Macro 탐색" UI 결과와의 구분**
Step 4에서 사용자에게 보여주는 macro 목록은 old/new 버전 간 **diff macro만**
필터한 결과이며 UI 표시 전용이다. `get_macro_file_list()`는 diff가 아니라
해당 rule의 **전체** 참조 macro를 반환해야 한다. 복사/컴파일 단계에서는
diff가 아닌 전체 macro closure가 대상이기 때문이다.

#### `get_version_from_filename(file_name) -> str`
단일 파일명에서 version 토큰만 뽑는 pure helper. `get_rule_file_list()`
내부와 필요시 orchestrator에서도 재사용 가능.

| 항목 | 설명 |
|---|---|
| Input `file_name` | `str` — RTD `.report` 원본 파일명 |
| Output | `str` — `_PC` 뒤, `.report` 앞의 version 토큰. 포맷에 맞지 않으면 빈 문자열 |

### 1.2 유지 (helper)
- `read_rule_source_text(host, login_user, home_dir_path, file_name) -> str`
- `read_rule_source_bytes(host, login_user, home_dir_path, file_name) -> bytes`
  — `svn_upload_custom.py`가 바이트 로드용으로 사용

### 1.3 제거/흡수
- `fetch_rule_source_file_names()` → `get_rule_file_list()` 내부로 흡수, 비공개화
- `parse_rule_catalog_entries()` → `get_rule_file_list()` 내부로 흡수, 비공개화
- `extract_macro_list()` → `get_macro_file_list()` 내부로 흡수, 비공개화
- `_strip_report_suffix()` → `get_version_from_filename()`로 교체

---

## 2. RTD Execution — `rtd_execution_custom.py`

퍼블릭 함수 이름은 이미 스펙과 일치하므로 **시그니처 유지**. 단,
**copy/compile 대상 수집 로직은 변경**된다.

- `execute_copy_action(db, task, payload) -> dict[str, str]`
- `execute_compile_action(db, task, payload) -> dict[str, str]`
- `execute_test_action(db, task, payload) -> dict[str, str]`

| 항목 | 설명 |
|---|---|
| Input `db` | `sqlalchemy.orm.Session` |
| Input `task` | `TestTask` — 실행 대상 RTD task, `task.target_name`은 target line |
| Input `payload` | `dict[str, Any]` — task 요청 payload (필요 시 `payload["payload"]`로 한 단계 unwrap) |
| Output `message` | 모니터 hover용 요약 문자열 |
| Output `raw_output` | 디버그/로그용 원격 실행 원문 (copy는 공백 허용) |
| Output (test 전용) `raw_outputs_by_rule` | `dict[str, str]` — rule별 raw 텍스트. `file_service`가 `line x rule` txt 파일로 저장 |

### 2.1 Copy / Compile 대상 범위 (변경)

**대상이 되는 것은**:
- 선택된 모든 rule의 **old version report** + **new version report** (양쪽 전부)
- 그리고 위 각 rule report가 **참조하는 모든 macro report의 합집합(closure)**

즉 "Step 4 Macro 탐색"에서 화면에 표시되는 macro 목록은 **old/new 버전 간
차이점(diff)만** 보여주는 UI 표시용이다. 실제 copy/compile 대상은
**diff가 아니라 각 rule이 실제로 참조하는 macro 전체**가 되어야 한다.

현재 구현(`_collect_macro_file_names`)이 `session_payload["selected_macros"]`
(=diff 결과)를 쓰고 있는 것은 잘못. 다만 `selected_macros` 키 자체를
버리지는 않고, **스키마를 확장해서 버전별 전체 macro 목록을 담도록**
바꾼다. Step 4 UI 표시는 그 중 diff만 필터해서 보여주는 것으로 역할을
명확히 구분한다.

### 2.2 session_payload 스키마 확장

execution 단계에서 catalog cache를 다시 뒤지거나 rule source를 재파싱하지
않아도 되도록, rule 선택 시점(`selected_rule_targets` 저장)과
Macro 탐색 시점(`selected_macros` 저장)에 필요한 모든 정보를
세션에 한 번만 쌓아 둔다.

#### `selected_rule_targets` — rule 파일명까지 함께 저장

**기존**

```json
{
  "rule_name": "RULE_A",
  "old_version": "v1",
  "new_version": "v2"
}
```

**신규**

```json
{
  "rule_name": "RULE_A",
  "old_version": "v1",
  "new_version": "v2",
  "old_file_name": "RULE_A_PCv1.report",
  "new_file_name": "RULE_A_PCv2.report"
}
```

- `old_file_name` / `new_file_name`은 rule 선택이 확정되는 시점
  (`rtd.py` save-session / catalog_service 호출 경로)에 catalog에서 조회해
  함께 기록한다.
- 이후 execution 단계는 catalog cache를 다시 읽지 않고 payload만으로
  copy 대상 파일명을 확정할 수 있다.

#### `selected_macros` — 버전별 전체 macro 보관

**기존(=diff 중심)**

```json
{
  "selected_macros": ["MACRO_X.report", "MACRO_Y.report"]
}
```
(diff 결과 리스트만 저장)

**신규(=버전별 전체 + diff 구분)**

```json
{
  "selected_macros": {
    "per_rule": [
      {
        "rule_name": "RULE_A",
        "old_version": "v1",
        "new_version": "v2",
        "old_macros": ["MACRO_X.report", "MACRO_Y.report", "MACRO_Z.report"],
        "new_macros": ["MACRO_X.report", "MACRO_Y2.report", "MACRO_Z.report"]
      }
    ],
    "diff_macros": {
      "old_only": ["MACRO_Y.report"],
      "new_only": ["MACRO_Y2.report"]
    }
  }
}
```

- `per_rule[*].old_macros` / `new_macros`는 해당 version의 rule report가
  참조하는 **전체 macro closure**. Step 4에서 `get_macro_file_list()`를
  호출한 결과를 그대로 저장한다.
- `diff_macros`는 UI(Step 4 Macro 확인 화면)에서 "old/new가 서로 다른
  macro만" 보여주기 위한 파생 필드. 실제 copy/compile에는 사용되지 않는다.

> Note: 최종 스키마 세부(필드명, per_rule/flat 중 어느 쪽)는 구현 시점에
> 확정. 핵심 요구사항은 "버전별 전체 macro 리스트 + diff 결과를 분리
> 보관"이다.

### 2.3 내부 helper 재설계

기존 `_collect_macro_file_names(session_payload)`, `_collect_rule_file_names(...)`
를 아래 2개로 대체한다. 세션 페이로드가 이미 파일명을 들고 있다는
전제이므로 DB/SSH 접근이 없다.

#### `_collect_rule_file_names_from_payload(session_payload) -> list[str]`

| 항목 | 설명 |
|---|---|
| Input | `session_payload["selected_rule_targets"]` — 각 항목에 `old_file_name`, `new_file_name` 포함 |
| Output | 선택 rule × (old, new) file_name 목록 (unique, rule 정렬 순서 보존) |

#### `_collect_macro_file_names_from_payload(session_payload) -> list[str]`

| 항목 | 설명 |
|---|---|
| Input | `session_payload["selected_macros"]["per_rule"]` — rule별 old/new macro 리스트 |
| Output | 모든 `old_macros` + `new_macros`의 합집합 (unique, 첫 등장순서 보존) |

- diff(`diff_macros`)는 무시하고 `per_rule[*].old_macros`, `new_macros`만
  이어붙여 중복 제거.
- Compile 우선순위는 기존 규칙("higher-priority macros appear earlier in
  the rule source, so compile starts from the lowest-priority end")을
  그대로 유지하므로 등장순서 보존이 중요.
- `per_rule` 구조가 없는 레거시 payload(=기존 `selected_macros`가 flat
  list)도 만나면, 호환 차원에서 flat list를 그대로 return 하도록
  fallback 분기만 추가.

이렇게 수집한 `macro_file_names`가 copy 대상(원격 cp)과 compile 대상
(`atm_compiler` 역순 호출)의 **단일 출처**가 된다.

### 2.4 각 action 적용

- `execute_copy_action`
  - `_collect_rule_file_names_from_payload()` + `_collect_macro_file_names_from_payload()` 호출
  - rule 파일은 `<dev_home>/` → `<target_home>/`로 cp
  - macro 파일은 `<dev_home>/../Macro/` → `<target_home>/../Macro/`로 cp
  - catalog cache 조회 경로(`_collect_rule_file_names`의 현 버전) 제거

- `execute_compile_action`
  - 같은 두 helper로 `rule_file_names`, `macro_file_names` 확보
  - rule_file_names → rule_names(version suffix 제거한 논리명) 추출해도 되고,
    기존 `_collect_selected_rule_names()`를 유지해도 됨
  - `macro_file_names`는 파일명 그대로 사용(`atm_compiler` 인자)
  - 기존 역순 컴파일 + rule 컴파일 순서 유지

- `execute_test_action`
  - 변경 없음(macro는 이미 compile 단계에서 처리되므로 test는 rule_names만 사용)

### 2.5 제거/수정 대상

- 기존 `_collect_macro_file_names(session_payload)` (diff 의존) — 제거
- 기존 `_collect_rule_file_names(db, user_id, line_name, session_payload)`
  (catalog cache 의존) — 제거. 대체 helper는 2.3의 payload-only 버전.
- catalog cache lookup이 사라졌으므로 `selected_rule_targets`에
  `old_file_name`/`new_file_name`이 비어 있는 경우 명확한 에러 메시지를
  내도록 한 줄 validation 추가.
- 위 변경에 맞춰 copy/compile의 monitor summary 문자열(`_format_copied_items_summary`,
  `_format_compile_items_summary`)도 `macro_file_names`가 전체 closure임을
  전제로 업데이트. 카운트 필드 의미가 "diff 수"에서 "전체 참조 macro 수"로
  바뀌므로 라벨은 유지하되 docstring 한 줄 갱신.

### 2.6 payload 기록 지점 (caller 쪽 동작)

신규 스키마는 execution 단계에서 "있다고 가정"하므로, 이를 실제로 넣어
주는 쪽도 같이 바꿔야 한다.

- **Rule 선택 단계** (`api/rtd.py`의 rule save + `catalog_service`의
  `find_rule_file_name_in_session`) :
  selected_rule_targets를 저장할 때 catalog에서 `old_file_name` /
  `new_file_name`을 찾아 함께 기록한다.
- **Macro 탐색 단계** (`catalog_service.compare_macros_by_rule_targets`
  + 이를 호출하는 API):
  현재 diff만 돌려주고 있는데, diff를 계산하기 위해 이미 old/new macro
  전체 리스트를 구하고 있으므로(`get_macro_list_by_rule_name` × 2),
  그 전체 결과를 `selected_macros.per_rule`에 함께 저장한다. **API 응답에도
  per-version 전체 macro를 포함시키고 프론트가 diff 렌더링을 담당**한다
  (Open Q #5: 결정 B). `diff_macros`는 응답에서 제거하고, 프론트
  `stores/rtd.js` + `components/rtd/StepMacroReview.vue`에서 old/new
  리스트로부터 직접 계산하여 렌더한다.

---

## 3. RTD Report — `rtd_report_custom.py`

### 3.1 리네이밍
`build_rtd_test_report_file()` → `build_rtd_test_report()`

| 항목 | 설명 |
|---|---|
| Input `tasks` | `list[TestTask]` — 완료된 RTD TEST/RETEST tasks (caller가 최신순 정렬) |
| Input `output_path` | `pathlib.Path` — 저장될 `.xlsx` 경로 |
| Input `fallback_major_change_items` | `dict[str, str] | None` — 현재 session의 rule별 주요 변경항목 (task payload보다 우선 적용) |
| Input `selected_rule_names` | `list[str] | None` — 결과서에 포함할 rule 필터 |
| Output | `Path` — 저장된 Excel 파일 경로 |

동작은 기존과 동일(행 단위 `line x rule_name`, `(line_name, rule_name)` 중복 제거).

---

## 4. ezDFS Catalog — `ezdfs_catalog_custom.py`

### 4.1 신규 퍼블릭 함수

#### `get_rule_file_list(host, login_user, home_dir_path) -> list[dict[str, str]]`
deployed 디렉토리 스캔 + 파싱을 하나로 합친 것.

| 항목 | 설명 |
|---|---|
| Input `host` | `HostConfig` |
| Input `login_user` | `str` |
| Input `home_dir_path` | `str` — 모듈 home. 내부에서 `<home>/repository/container/dfsdev/deployed`로 확장 |
| Output | `list[dict[str, str]]` — `{"file_name", "rule_name", "version"}` |
| 정렬 | `rule_name` → `version` |

파일명 포맷: `{rule_name}-ver.{version}.{timestamp}.rul`. timestamp는 버려지고
`version`은 `ver.` 접두어를 포함한 채 반환된다.

#### `get_backup_file_list(host, login_user, home_dir_path) -> list[dict[str, str]]`
backup 디렉토리(`<home>/repository/container/dfsdev/backup`)에서 같은 스키마로 반환.
old version 후보 조회용.

| 항목 | 설명 |
|---|---|
| Input/Output | `get_rule_file_list()`와 동일, 단 backup 디렉토리를 스캔한다 |

#### `get_version_from_filename(file_name) -> str`
단일 파일명에서 `ver.x.y.z` 부분만 추출. 포맷 불일치 시 빈 문자열.

| 항목 | 설명 |
|---|---|
| Input `file_name` | `str` — ezDFS `.rul` 파일명 |
| Output | `str` — 버전 토큰(`ver.` 포함) 또는 `""` |

#### `get_subrule_file_list(host, login_user, home_dir_path, rule_file_name, catalog_files=None) -> list[str]`
하나의 deployed ezDFS rule 파일이 **재귀적으로** 참조하는 모든 sub rule
이름 목록을 반환한다. 현재 `extract_sub_rule_list_from_rule_text()` +
`resolve_recursive_sub_rule_list()` 2-step을 하나로 합친 것.

| 항목 | 설명 |
|---|---|
| Input `host` | `HostConfig` — ezDFS 모듈 파일을 가진 원격 host |
| Input `login_user` | `str` — SSH 로그인 계정 |
| Input `home_dir_path` | `str` — 모듈 home. 내부에서 deployed 디렉토리로 확장 |
| Input `rule_file_name` | `str` — 탐색 시작점이 되는 root rule의 `.rul` 파일명 (`get_rule_file_list()` 결과의 `file_name`) |
| Input `catalog_files` | `list[dict] \| None` — caller가 이미 `get_rule_file_list()`로 확보해 둔 catalog. 전달되면 내부에서 재조회하지 않고 재사용, `None`이면 내부에서 1회 조회한다. (Open Q #6: 결정 B) |
| Output | `list[str]` — 재귀적으로 발견한 **sub rule의 rule_name 목록** (unique, 첫 등장순서 보존) |

**중요 — 반환 값은 rule_name (file_name이 아님)**
- 반환되는 각 항목은 논리적 rule 이름이며, 실제 파일명은 `{rule_name}.rul`
  컨벤션을 따른다.
- 실제 deployed 파일명은 `{rule_name}-ver.{version}.{timestamp}.rul` 형태로
  timestamp 토큰이 붙어 있어 완전히 같지 않다. 호출자가 실제 파일을
  로드해야 할 땐 catalog(`get_rule_file_list()`)에서 rule_name 매칭으로
  `file_name`을 다시 조회해야 한다. 이 매칭은 함수 내부에서도 재귀 탐색을
  위해 사용된다.

동작:
1. `catalog_files`가 제공되면 그걸 재사용, 아니면 내부에서
   `get_rule_file_list(host, login_user, home_dir_path)` 1회 호출로 catalog 확보
2. `rule_file_name`의 본문을 `read_rule_source_text()`로 읽음
3. 본문의 각 line에서 `<name>.rul` 참조를 뽑아 rule_name 후보 수집
   (주석 `//`, `#`, `;` 제거, 중복 제거, 첫 등장순서 보존)
4. 각 rule_name에 대응하는 catalog의 `file_name`을 찾아 같은 과정을 재귀
   (이미 방문한 rule_name은 skip)
5. 전체 traversal에서 나온 rule_name 합집합을 첫 등장순서대로 반환
6. 실패(SSH/파일 읽기)는 개별 분기에서 skip하여 가능한 범위까지 수집

### 4.2 유지 (helper, 현 이름 그대로)
- `read_rule_source_text(host, login_user, home_dir_path, file_name) -> str`
- `read_rule_source_bytes(host, login_user, home_dir_path, file_name) -> bytes`
- `find_latest_backup_version(backup_catalog_files, rule_name, excluded_version="") -> str`

이 3개는 `customFunction.md`에는 없지만 orchestrator와 `svn_upload_custom.py`
가 실제로 호출하고 있으므로 퍼블릭 helper로 남긴다. (`extract_sub_rule_list_from_rule_text`
와 `resolve_recursive_sub_rule_list`는 아래 4.3으로 이동 — `get_subrule_file_list`
내부에 흡수된다.)

### 4.3 제거/흡수
- `fetch_rule_source_file_names()` → `get_rule_file_list()`에 흡수
- `fetch_backup_rule_source_file_names()` → `get_backup_file_list()`에 흡수
- `parse_rule_catalog_entries()` → 양 신규 함수 내부로 흡수, 비공개 `_parse_rule_catalog_entries()`로만 보존 (Open Q #1: 결정 B — public export 하지 않음)
- `extract_sub_rule_list_from_rule_text()` → `get_subrule_file_list()`의 내부 line-parser(`_extract_sub_rule_names_from_text()`)로 격하
- `resolve_recursive_sub_rule_list()` → `get_subrule_file_list()`로 흡수 (caller는 rule text/ catalog를 직접 넘기지 않고 `rule_file_name`만 넘기면 된다)
- `_deployed_dir_from_home`, `_backup_dir_from_home`, `_version_sort_key`, `_find_catalog_file_name_by_rule_name` → 그대로 내부 helper

> 주의: `catalog_service._normalize_ezdfs_catalog_entries()`의 "session cache에
> 문자열 리스트가 섞여 들어온 레거시 케이스를 복구"하는 분기는 제거한다
> (Open Q #1: 결정 B). `_normalize_ezdfs_catalog_entries`는 이미 dict
> 리스트인 payload만 취급하도록 단순화하고, `parse_ezdfs_rule_catalog_entries`
> import는 삭제한다.

---

## 5. ezDFS Execution — `ezdfs_execution_custom.py`

### 5.1 리네이밍
`execute_ezdfs_test_action()` → `execute_test_action()`

| 항목 | 설명 |
|---|---|
| Input `db` | `Session` |
| Input `task` | `TestTask` — ezDFS TEST/RETEST task |
| Input `payload` | `dict[str, Any]` — 요청 payload. `module_name`/`rule_name`은 payload 또는 `payload["payload"]`에서 꺼낸다 |
| Output `message` | 모니터 요약 |
| Output `raw_output` | 원격 `ezDFS_test` stdout |
| Output `test_command` | 실행된 명령 문자열. `_meta.txt`에 저장 |

내부 helper(`_get_ezdfs_module_context`, `_run_ezdfs_test_binary`)는 그대로.

---

## 6. ezDFS Report — `ezdfs_report_custom.py`

### 6.1 리네이밍
`build_ezdfs_test_report_file()` → `build_ezdfs_test_report()`

| 항목 | 설명 |
|---|---|
| Input `tasks` | `TestTask | list[TestTask]` — 단일 혹은 복수 완료 task |
| Input `output_path` | `Path` |
| Input `selected_rule_names` | `list[str] | None` — rule 필터 (선택 rule당 최신 task 1건만 기록) |
| Input `fallback_major_change_items` | `dict[str, str] | None` |
| Output | `Path` — 저장된 `.xlsx` 경로 |

동작 변경 없음.

---

## 7. Backend 수정 계획 (call site)

### 7.1 `backend/app/services/catalog_service.py`
Import 블록 교체:

```python
# before
from app.services.ezdfs_catalog_custom import (
    fetch_backup_rule_source_file_names as fetch_ezdfs_backup_rule_source_file_names,
    fetch_rule_source_file_names as fetch_ezdfs_rule_source_file_names,
    find_latest_backup_version,
    parse_rule_catalog_entries as parse_ezdfs_rule_catalog_entries,
    read_rule_source_text as read_ezdfs_rule_source_text,
    resolve_recursive_sub_rule_list,
)
from app.services.rtd_catalog_custom import (
    extract_macro_list,
    fetch_rule_source_file_names,
    parse_rule_catalog_entries,
    read_rule_source_text,
)
```

```python
# after
from app.services.ezdfs_catalog_custom import (
    get_rule_file_list as get_ezdfs_rule_file_list,
    get_backup_file_list as get_ezdfs_backup_file_list,
    get_subrule_file_list as get_ezdfs_subrule_file_list,
    find_latest_backup_version,
    read_rule_source_text as read_ezdfs_rule_source_text,
)
from app.services.rtd_catalog_custom import (
    get_macro_file_list,
    get_rule_file_list,
)
```

호출 라인 교체:

- `_fetch_rtd_catalog_over_ssh()` 내부 312-313 라인의
  `fetch_rule_source_file_names(...)` + `parse_rule_catalog_entries(...)`
  2-step → `catalog_files = get_rule_file_list(host, config.login_user, config.home_dir_path)` 1-step.
- `_fetch_ezdfs_catalog_over_ssh()` 내부 335-339 라인의 deployed/backup
  2-step을 각각 `get_ezdfs_rule_file_list(...)`, `get_ezdfs_backup_file_list(...)`
  1-step으로.
- `get_macro_list_by_rule_name()` 내부 146-147 라인:
  `read_rule_source_text() + extract_macro_list()` 2-step →
  `get_macro_file_list(host, config.login_user, config.home_dir_path, file_name)` 1-step.
  (내부 `read_rule_source_text` import는 더 이상 필요 없음)
- `get_ezdfs_sub_rules()` 내부 (현재 213-226 라인):
  `read_ezdfs_rule_source_text()` + `resolve_recursive_sub_rule_list()`
  2-step → `get_ezdfs_subrule_file_list(host, config.login_user, config.home_dir_path, resolved_file_name, catalog_files=catalog.get("files", []))` 1-step.
  caller가 이미 `catalog`를 보유하고 있으므로 optional `catalog_files`로
  넘겨 재조회를 막는다(Open Q #6: 결정 B). `selected_entry` /
  `preferred_version` 산출 로직은 root rule의 `file_name`을 구하기 위해
  그대로 유지한다(함수 내부 재귀는 catalog 기반이므로 root file 확정만
  caller에서 수행).
  (반환은 **rule_name 목록**이므로 기존과 동일하게 프론트가 받는다.)
- `_normalize_ezdfs_catalog_entries()` — 문자열 리스트 입력을
  `parse_ezdfs_rule_catalog_entries`로 복구하던 레거시 분기 **제거**
  (Open Q #1: 결정 B). 이미 dict list인 payload만 취급하도록 단순화하고,
  `parse_ezdfs_rule_catalog_entries` import도 삭제.
- `compare_macros_by_rule_targets()` 응답 포맷 변경 (Open Q #5: 결정 B):
  기존에는 diff 리스트 중심으로 반환했으나, 신규에는 `per_rule[*]`에
  `{rule_name, old_version, new_version, old_macros, new_macros}`를
  포함시켜 반환한다. `diff_macros`는 제거하고 프론트에서 계산.
  동일한 응답 페이로드를 `selected_macros` 키로 `RuntimeSession`에 upsert.

### 7.2 `backend/app/services/task_worker.py`
Import 라인 (line 21, 24-26) 수정:

```python
# before
from app.services.ezdfs_execution_custom import execute_ezdfs_test_action
from app.services.rtd_execution_custom import (
    execute_compile_action,
    execute_copy_action,
    execute_test_action,
)
```

```python
# after
from app.services import ezdfs_execution_custom, rtd_execution_custom
```

호출부(현재 line 136-144):

```python
# before
return execute_copy_action(db, task, payload)
return execute_compile_action(db, task, payload)
return execute_test_action(db, task, payload)   # RTD
...
return execute_ezdfs_test_action(db, task, payload)
```

```python
# after
return rtd_execution_custom.execute_copy_action(db, task, payload)
return rtd_execution_custom.execute_compile_action(db, task, payload)
return rtd_execution_custom.execute_test_action(db, task, payload)
...
return ezdfs_execution_custom.execute_test_action(db, task, payload)
```

모듈 경로 참조로 바꿔야 RTD와 ezDFS의 동명 `execute_test_action`
충돌을 피할 수 있다.

### 7.3 `backend/app/services/file_service.py`

- Line 13-14 import:
  - `build_ezdfs_test_report_file` → `build_ezdfs_test_report`
  - `build_rtd_test_report_file` → `build_rtd_test_report`
- Line 111, 125 호출부도 동일하게 교체.

### 7.4 `backend/app/services/file_download.py`

- Line 13, 15 import 변경 (동일).
- Line 146, 207 호출부 변경.
- Line 223 docstring 내 이름 언급도 `build_rtd_test_report`로 업데이트.

### 7.5 `backend/app/services/svn_upload_custom.py`

- Line 29, 32: `read_rule_source_bytes` import는 유지(신규 스펙 바깥의
  helper이므로 이름 유지).
- 다른 변경 없음.

### 7.6 Frontend
Open Q #5(결정 B) 영향으로 macro diff 렌더링을 프론트가 담당한다.
- `frontend/src/stores/rtd.js` — `compareMacrosByRuleTargets` 응답
  schema 교체: 기존 `diff_macros` 기반 store 필드를 `selected_macros.per_rule`
  (old_macros / new_macros 전체) 기반으로 교체.
- `frontend/src/components/rtd/StepMacroReview.vue` — old/new macro
  리스트를 받아 diff(old_only, new_only, common)를 computed로 계산해서
  렌더링. 기존 서버제공 diff는 제거.
- Session 복원 시에도 동일 schema(`selected_macros.per_rule` +
  파생 diff)를 사용하므로 리프레시 동작 유지.
- 그 외 custom 함수 리네이밍은 backend 내부 경계 교체로 REST 계약에
  영향 없음.

### 7.7 Docs
- `CLAUDE.md`의 "Custom Implementation Pattern" 섹션 함수 예시를
  `get_rule_file_list / get_macro_file_list / get_subrule_file_list /
  get_version_from_filename`, `build_*_test_report` 새 이름으로 업데이트.
- `backend/README.md`의 custom hook 표도 동일 반영 (ezDFS catalog 쪽에
  `get_subrule_file_list` 행 추가).
- `docs/customFunction.md`의 ezDFS catalog 섹션에 `4. get_subrule_file_list`
  항목이 이미 추가되어 있는지 확인/동기화.

---

## 8. 단계별 작업 순서 (권장)

1. **RTD catalog 리네이밍 + 병합** (`rtd_catalog_custom.py`)
2. `catalog_service.py`의 RTD 경로 import/호출 교체 → uvicorn 재기동으로 import error 확인
3. **ezDFS catalog 리네이밍 + 병합** (`ezdfs_catalog_custom.py`) — `get_subrule_file_list` 포함
4. `catalog_service.py`의 ezDFS 경로 import/호출 교체
   - `_normalize_ezdfs_catalog_entries` 레거시 분기 제거 (Open Q #1)
   - `get_ezdfs_sub_rules`에서 `catalog_files` 전달 (Open Q #6)
5. **RTD execution 스키마 적용** (`rtd_execution_custom.py`)
   - `_collect_rule_file_names_from_payload()`,
     `_collect_macro_file_names_from_payload()` payload-only 헬퍼로 교체
   - copy/compile 대상이 full closure(per_rule old/new macros)가 되도록 확장
6. **Rule 선택 단계 payload 기록 확장**
   - `catalog_service` / `api/rtd.py` rule save 경로에서
     `selected_rule_targets[*].old_file_name`, `new_file_name` 기록
7. **`compare_macros_by_rule_targets` 응답·session upsert 변경** (Open Q #5 결정 B)
   - 응답에 `per_rule[*].old_macros / new_macros` 전체 리스트 포함
   - 동일 페이로드를 `selected_macros`로 `RuntimeSession`에 upsert
   - `diff_macros` 응답 필드 제거
8. **Frontend 대응** (Open Q #5 결정 B)
   - `stores/rtd.js` 응답 처리 변경
   - `components/rtd/StepMacroReview.vue`에서 diff 계산·렌더
9. **ezDFS execution 리네이밍** (`execute_test_action`)
10. `task_worker.py` import/호출 교체 (모듈 경로 참조)
11. **RTD/ezDFS report 리네이밍** (`build_rtd_test_report`, `build_ezdfs_test_report`)
12. `file_service.py`, `file_download.py` import/호출 교체
13. `svn_upload_custom.py` import 확인 (read_rule_source_bytes 유지)
14. 수동 smoke test: RTD Step 3(rule/version 조회), Step 4(macro 탐색 +
    diff 렌더링), Step 6(복사/컴파일/테스트/결과서), ezDFS Step 2/3/4 전체 동일 시나리오

---

## 9. Open Questions — 결정 완료

1. **`parse_rule_catalog_entries`를 public으로 남길지 — 결정: B**
   - `_normalize_ezdfs_catalog_entries()`의 레거시 문자열 리스트 분기를
     제거한다. ezDFS catalog 모듈은 `_parse_rule_catalog_entries()`만 내부
     helper로 유지하고 public export하지 않는다.
   - 영향: Section 4.3, Section 7.1 (ezDFS catalog 경로 refactor 시 함께
     처리).
2. **`get_macro_file_list` 인자 형태 — 결정: A**
   - 시그니처 `(host, login_user, home_dir_path, rule_file_name)` 확정.
     1-step 원칙(#2)과 일관. 내부에서 `read_rule_source_text()`를 호출해서
     rule_text를 확보한 뒤 파싱한다.
3. **`get_version_from_filename`의 위치 — 결정: A**
   - 각 `*_catalog_custom.py`에 시스템 고유 포맷으로 둔다. 포맷 의존성이
     custom 계층에 묶이는 것이 offline 교체 원칙과 일관.
4. **macro closure 계산 시점 — 결정: Step 4 저장 (기존 확정)**
   - Step 4(Macro 탐색) 시점에 old/new 버전별 전체 macro 리스트를
     `selected_macros.per_rule`에 저장. execution은 SSH 없이 payload만으로
     대상 파일을 확정한다.
5. **`compare_macros_by_rule_targets` 응답 포맷 — 결정: B**
   - 응답에도 per-version 전체 macro를 포함시킨다. 프론트는 diff 렌더링을
     직접 담당한다.
   - 영향:
     - 백엔드 `catalog_service.compare_macros_by_rule_targets()` 응답에
       `per_rule[*].old_macros / new_macros` 전체 리스트를 포함.
       `diff_macros`는 유지 혹은 제거(프론트에서 계산할 수 있으므로 제거 권장).
     - 백엔드는 동일 응답 페이로드를 `selected_macros` 키로
       session에 upsert (2.2 신규 schema 그대로).
     - 프론트(`stores/rtd.js` + `components/rtd/StepMacroReview.vue`)에서
       per-version 전체 macro → diff 계산 로직 추가.
     - 해당 Frontend 변경은 Section 7.6 참고.
6. **`get_subrule_file_list` 내부 catalog 조회 반복 여부 — 결정: B**
   - 시그니처에 optional `catalog_files: list[dict] | None = None` 추가.
     caller가 이미 catalog를 들고 있으면 그대로 전달, 없으면 내부에서
     `get_rule_file_list()` 1회 호출.
   - 영향: Section 4.1 signature 갱신, Section 7.1
     `get_ezdfs_sub_rules()` 호출부에서 caller가 보유한 catalog를 전달.
