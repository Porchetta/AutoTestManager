# CLAUDE.md — AutoTestManager

## Project Purpose

AutoTestManager is an internal web application for managing and executing
automated tests against RTD (Rule Test Dispatcher) and ezDFS rule systems.
It runs in an **offline-capable** enterprise environment (RHEL 7.9),
deployed via Docker images. The application enables MSS developers to:

- Select business units, lines, rules, and versions through a guided wizard
- Copy rule files to target servers, compile them, and run tests via SSH
- Monitor test execution across multiple target lines in parallel
- Generate Excel summary reports and download raw test output
- Commit updated rule sources via SVN after successful test passes

## Architecture Overview

```
Frontend (Vue 3 SPA)        Backend (FastAPI)        Remote Hosts
  +-----------+            +-----------+           +----------+
  | Vue 3     |  REST/JSON | FastAPI   |    SSH    | RTD/ezDFS|
  | Pinia     | ---------> | SQLAlchemy| --------> | servers  |
  | Vite      |            | SQLite    |  Paramiko |          |
  +-----------+            +-----------+           +----------+
  Port 4203                Port 10223
```

### Frontend Stack
- Vue 3 with Composition API (`<script setup>`)
- Pinia for state management (setup function syntax)
- Vue Router with JWT-guarded navigation
- Axios with centralized interceptors (`api.js`)
- Custom CSS design system modularized under `src/styles/`
  with CSS custom properties and light/dark theme toggle

### Backend Stack
- FastAPI with router-based API modules under `/api/`
- SQLAlchemy 2.0 with `Mapped[type]` + `mapped_column()` pattern
- SQLite database at `backend/data/autotestmanager.db`
- Pydantic v2 for request/response validation
- JWT auth via python-jose, passwords hashed with passlib+bcrypt
- Paramiko for SSH connections to remote test servers
- openpyxl for Excel report generation
- Background tasks run in daemon threads (not Celery/RQ)

### Deployment
- Docker images built on online machine, transferred via tar.gz
- Source is mounted into the container at runtime (not baked in)
- Dev mode: uvicorn --reload + Vite HMR
- Prod mode: nginx serves static frontend, proxies `/api/*` to backend

## Development Setup

### Backend
```bash
cd backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh      # Creates .venv, installs requirements.txt
./run-dev.sh        # Starts uvicorn on port 10223
```

Default admin: `admin` / `admin1234`

API docs: http://127.0.0.1:10223/docs

### Frontend
```bash
cd frontend
cp .env.example .env
npm install
npm run dev         # Starts Vite on port 4203
```

Environment: `VITE_API_BASE_URL=http://127.0.0.1:10223`

## Project Structure

### Backend
```
backend/app/
  main.py               # FastAPI app, lifespan, CORS, router registration
  api/                   # Route handlers (thin controllers)
    auth.py              # Login, signup, password change
    admin.py             # User/Host/RTD/ezDFS config CRUD (admin-only)
    rtd.py               # RTD catalog, session, execution, download APIs
    ezdfs.py             # ezDFS catalog, session, execution, download APIs
    mypage.py            # User history, result downloads
    deps.py              # FastAPI dependencies (get_db, get_current_user)
  core/
    config.py            # Settings from .env via pydantic-settings
                         #   (includes cors_origins list)
    security.py          # JWT encode/decode, password hashing
    responses.py         # success_response() wrapper
    exceptions.py        # Domain exceptions + FastAPI exception handlers
  db/
    session.py           # Engine, SessionLocal, Base, init_db, legacy migrations
  models/
    entities.py          # All SQLAlchemy models (User, HostConfig, RtdConfig,
                         #   EzdfsConfig, TestTask, RuntimeSession, DashboardLike)
  schemas/               # Pydantic request/response schemas
  services/
    # Orchestrators (no SSH / no file-format parsing)
    catalog_service.py   # RTD/ezDFS catalog orchestration
    task_service.py      # Task CRUD, status transitions
    task_worker.py       # Background worker loop, per-task lifecycle
    task_queue.py        # In-memory queue primitives (per line / per module)
    file_service.py      # Raw file / summary generation paths
    file_download.py     # Download aggregation (latest-per-line, reports)
    session_service.py   # Runtime session CRUD (per-user, per-test-type)
    ssh_runtime.py       # SSH connection pool, parallel limit detection
    bootstrap.py         # Default admin seed, storage directory creation

    # Custom hooks — offline adaptation points
    rtd_catalog_custom.py
    rtd_execution_custom.py
    rtd_report_custom.py
    ezdfs_catalog_custom.py
    ezdfs_execution_custom.py
    ezdfs_report_custom.py
    svn_upload_custom.py
  utils/
    enums.py             # TestType, ActionType, TaskStatus, TaskStep
    constants.py         # TARGET_SUFFIX, RULE_ERROR_ITEM, bash prefix, etc.
    ssh_helpers.py       # build_clean_bash_command, run_remote_command,
                         #   extract_session_payload (shared across custom files)
    naming.py            # normalize_target_line_name, path sanitization
```

### Frontend
```
frontend/src/
  api.js                 # Axios instance, interceptors, apiGet/Post/Put/Delete
  main.js                # App bootstrap
  App.vue                # Root component (global toasts, modals)
  router/index.js        # Route definitions and navigation guards

  styles/
    tokens.css           # CSS custom properties (colors, spacing, typography)
    base.css             # html/body reset, base typography
    layout.css           # Page grid, shell, header/sidebar
    panels.css           # Panel / card / article surfaces
    forms.css            # Inputs, selects, buttons, field groups
    components.css       # Tables, badges, modals, toasts, tabs
    responsive.css       # Breakpoints and responsive overrides
    pages/
      dashboard.css
      rtd.css
      admin.css
      monitor.css
      mypage.css
  style.css              # Entry: @imports all files under styles/

  composables/
    useTaskPolling.js    # onMounted/onBeforeUnmount-driven polling helper
                         #   + waitForTaskTerminalStatus helper

  stores/
    auth.js              # JWT token, user info, localStorage persistence
    rtd.js               # RTD wizard state, session save/restore, task polling
    ezdfs.js             # ezDFS wizard state, session save/restore, task polling
    admin.js             # Admin-only data (users, hosts, configs, ssh-limits)
    ui.js                # Global loading, error, confirm dialog
    theme.js             # Dark/light theme toggle

  layouts/
    MainLayout.vue       # Sidebar + header + content shell

  views/                 # Thin shells that orchestrate child components
    LoginView.vue
    SignupView.vue
    DashboardView.vue    # Uses useTaskPolling to refresh queue snapshot
    RTDView.vue          # RTD 6-step wizard shell (~200 lines)
    EzDFSView.vue        # ezDFS 4-step wizard shell (~200 lines)
    AdminView.vue        # Admin tab shell (~60 lines) — delegates to 4 tabs
    MyPageView.vue       # Password change + result history

  components/
    SidebarNav.vue
    StatusBadge.vue
    SvnResultModal.vue   # Shared teleport modal (RTD + ezDFS)
    rtd/
      StepBusinessUnit.vue
      StepLine.vue
      StepRuleSelect.vue
      StepMacroReview.vue
      StepTargetLine.vue
      StepExecute.vue
      TargetMonitor.vue
      SvnUploadForm.vue
      monitorHelpers.js
    ezdfs/
      StepModule.vue
      StepRuleSelect.vue
      StepSubRuleReview.vue
      StepExecute.vue
      SvnUploadForm.vue
    admin/
      UsersTab.vue
      HostsTab.vue
      RtdConfigsTab.vue
      EzdfsConfigsTab.vue
      sortHelpers.js     # sortItems(), useSort(defaultKey) composable
```

## Custom Implementation Pattern (*_custom.py)

The `*_custom.py` files are the primary extension points for offline
environment adaptation. They follow a three-layer pattern for each test
system (RTD and ezDFS):

### 1. Catalog Custom
`rtd_catalog_custom.py`, `ezdfs_catalog_custom.py`
- Discover and parse rule files from remote servers via SSH
- Key functions: `fetch_rule_source_file_names()`, `parse_rule_catalog_entries()`,
  `read_rule_source_text()`, `extract_macro_list()` (RTD) /
  `extract_sub_rule_list_from_rule_text()` (ezDFS)

### 2. Execution Custom
`rtd_execution_custom.py`, `ezdfs_execution_custom.py`
- Run copy, compile, and test commands on remote hosts
- Key functions: `execute_copy_action()`, `execute_compile_action()`,
  `execute_test_action()` / `execute_ezdfs_test_action()`

### 3. Report Custom
`rtd_report_custom.py`, `ezdfs_report_custom.py`
- Generate Excel reports from completed test tasks
- Key functions: `build_rtd_test_report_file()` / `build_ezdfs_test_report_file()`

### Call Chain
```
API Route -> catalog_service.py -> *_catalog_custom.py -> ssh_runtime.py
API Route -> task_service.py    -> task_worker.py      -> *_execution_custom.py -> ssh_runtime.py
API Route -> file_service.py    -> *_report_custom.py
```

**Rule**: the orchestrator services (`catalog_service`, `task_service`,
`task_worker`, `file_service`, `file_download`) must NOT contain SSH
commands or file-format parsing. That logic belongs in the `*_custom.py`
files and in `utils/ssh_helpers.py`.

## Coding Conventions

### Backend
- All modules start with `from __future__ import annotations`
- SQLAlchemy uses `Mapped[type]` with `mapped_column()` (SA 2.0 style)
- Pydantic v2 with `model_config = ConfigDict(from_attributes=True)`
- API responses wrapped in `success_response({"key": value})`
- Error responses: raise a domain exception from `core/exceptions.py`
  (or `HTTPException` for ad-hoc cases). Handlers in `main.py` normalize
  the payload to `{"success": False, "error": {...}}`
- SSH commands run through `utils/ssh_helpers.build_clean_bash_command()`
  (always `bash --noprofile --norc -lc <quoted-cmd>`)
- Timestamps are always UTC via `datetime.now(timezone.utc)`
- String enums in `utils/enums.py` for TestType, ActionType, TaskStatus, TaskStep
- Prefer specific exception types (`paramiko.SSHException`,
  `json.JSONDecodeError`, `OSError`). Broad `except Exception` is allowed
  only in the top-level task worker loop and the SSH probe fallback.

### Frontend
- Vue 3 `<script setup>` with Composition API exclusively
- Pinia stores use setup function syntax (not options API)
- API calls via `apiGet()`, `apiPost()`, `apiPut()`, `apiDelete()` from `api.js`
- File downloads via `downloadFile()` which handles Content-Disposition
- Session persistence: stores save state to backend on each step change
- Polling: use `useTaskPolling(tickFn)` from `composables/useTaskPolling.js`
  instead of hand-rolled `setInterval`/`clearInterval`
- UI labels are in Korean; do not change existing labels without approval
- Theme: CSS custom properties with `:root` (light) and `[data-theme="dark"]`
- CSS lives under `src/styles/` modules — `style.css` is an entry file
  that only contains `@import` statements
- No TypeScript, no component library, no form validation library

## Critical Patterns to Preserve

1. **Session restoration**: Users expect page refresh to restore their
   exact wizard state. The `RuntimeSession` table stores per-user,
   per-test-type JSON. Both frontend stores and backend `session_service`
   participate. Breaking this flow loses user work.

2. **Custom file boundary**: All SSH commands and file-format parsing
   must stay in `*_custom.py` files (or shared helpers in
   `utils/ssh_helpers.py`). The orchestrator services must never import
   `paramiko` or contain raw SSH logic.

3. **Background task threading**: Tasks run in daemon threads via
   `task_worker.py`. The worker opens its own DB session. Never use a
   request-scoped session inside background threads.

4. **Queue serialization**: RTD tasks for the same user+line are queued
   via in-memory queues in `task_queue.py` (using `threading.Condition`).
   ezDFS tasks queue per module. This prevents SSH connection flooding
   on remote hosts.

5. **Target line naming**: RTD target lines use `{line_name}_TARGET`
   suffix to distinguish from the dev line. The `TARGET_SUFFIX` constant
   in `utils/constants.py` and `normalize_target_line_name()` in
   `utils/naming.py` are the single source of truth.

6. **Offline deployment**: No external CDN, no npm registry access at
   runtime. Docker images carry all dependencies; source is mounted.

7. **Component decomposition boundary**: `views/*.vue` files are thin
   shells that hold wizard step state and render child components from
   `components/{rtd,ezdfs,admin}/`. Do not let views grow back into
   monolithic files — add new behavior to the relevant child component
   or extract a new one.

## Data Storage

- SQLite DB: `backend/data/autotestmanager.db`
- Result files: `backend/data/results/`
  - RTD raw: `rtd/raw/{user_id}/` (txt files + index.json)
  - RTD reports: `rtd/reports/{user_id}/`
  - ezDFS raw: `ezdfs/raw/{user_id}/`
  - ezDFS reports: `ezdfs/reports/{user_id}/`
- Admin alerts: `backend/data/logs/admin_alert.log`

## Existing Documentation

- `README.md` — Project-level overview and quick start
- `backend/README.md` — Backend architecture and custom hook guide
- `frontend/README.md` — Frontend architecture and component guide
- `docs/plan.md` — Feature requirements (Korean)
- `docs/Back.md` — Backend API contract and implementation specs (Korean)
- `docs/Front.md` — Frontend design specs (Korean)

---

## Refactoring Status

### Phase 1 — Quick Wins ✅ Complete

| # | Item | Outcome |
|---|------|---------|
| 1.1 | Extract duplicated utilities | `utils/ssh_helpers.py` (bash builder, remote runner, session payload), `utils/naming.py` (target line normalization) |
| 1.2 | Extract magic strings | `utils/constants.py` (`TARGET_SUFFIX`, `RULE_ERROR_ITEM`, bash prefix) |
| 1.3 | Custom exception classes | `core/exceptions.py` (`SSHConnectionError`, `RemoteCommandError`, `ConfigNotFoundError`, `TaskConflictError`, `CatalogError`) + FastAPI handlers |
| 1.4 | Narrow exception catches | 36 → 2 `except Exception` (task-worker top-level + SSH probe fallback). Replaced with specific types |
| 1.5 | Configurable CORS origins | `cors_origins` field on `Settings`, read from `CORS_ORIGINS` env var |

### Phase 2 — Component Decomposition ✅ Complete

| # | Item | Before → After |
|---|------|----------------|
| 2.1 | `RTDView.vue` | 1295 → ~200 lines; 8 components under `components/rtd/` |
| 2.2 | `AdminView.vue` | 1298 → ~60 lines; 4 tab components + `admin.js` store + `sortHelpers.js` |
| 2.3 | `EzDFSView.vue` | 756 → ~200 lines; 4 step components under `components/ezdfs/` |
| 2.4 | `task_service.py` | 707 → `task_service.py` (CRUD) + `task_worker.py` (daemon loop) + `task_queue.py` (queue primitives) |
| 2.5 | `file_service.py` | 572 → `file_service.py` (generation) + `file_download.py` (aggregation) |
| 2.6 | Store composables | `composables/useTaskPolling.js` (shared polling + `waitForTaskTerminalStatus`) |
| 2.7 | `style.css` | 3017 → 21-line entry; modules under `src/styles/` + `src/styles/pages/` |

### Phase 3 — Architecture Improvements (not started)

| # | Item | Description |
|---|------|-------------|
| 3.1 | pytest test suite | Add `backend/tests/` with conftest, test auth/admin/catalog/task/file modules |
| 3.2 | Structured logging | Replace ad-hoc file writes with Python `logging` module; add request ID middleware |
| 3.3 | Alembic migrations | Replace `_ensure_legacy_columns()` with proper Alembic migration history |
| 3.4 | TypeScript migration | Incremental: composables → stores → views; add type definitions for API responses |
| 3.5 | Test system protocol | Abstract RTD/ezDFS into a common `TestSystemCatalog`/`TestSystemExecution`/`TestSystemReport` protocol to reduce branching in orchestrator services |
| 3.6 | SSH credential encryption | Encrypt `HostConfig.login_password` at rest using Fernet symmetric encryption |
