# AutoTestManager — Frontend

Vue 3 + Vite + Pinia 기반 SPA.
RTD / ezDFS 위저드, 결과 조회, Admin Console 을 한 화면 안에서 제공합니다.

> 상위 프로젝트 개요는 [루트 README](../README.md), 전체 아키텍처 가이드는
> [`../CLAUDE.md`](../CLAUDE.md) 를 참고하세요.

---

## 빠른 시작

공식 개발 실행은 루트의 Docker 스크립트를 사용합니다.

```bash
cd ..
./deploy/run-dev.sh
```

로컬에서 프론트엔드만 수동 실행할 때:

```bash
cd frontend
cp .env.example .env      # VITE_API_BASE_URL=http://127.0.0.1:10223
npm install
npm run dev               # Vite dev server, port 4203
```

> `frontend/.env` 는 git에서 제외되는 로컬 전용 파일입니다. Docker 실행
> (`deploy/run-dev.sh`)을 사용하는 경우 별도로 만들 필요가 없습니다.
> backend 쪽 환경값은 루트의 `backend.dev.env` / `backend.prod.env` 에서
> 관리합니다 (자세한 내용은 [상위 README](../README.md#환경-파일-구조)).

| | |
|---|---|
| Dev URL | `http://127.0.0.1:4203` |
| Backend | `http://127.0.0.1:10223` (via `VITE_API_BASE_URL`) |
| DB Web | `http://127.0.0.1:8080` (backend 컨테이너의 sqlite-web) |

프로덕션 빌드:

```bash
npm run build             # dist/ 생성
npm run preview           # 로컬에서 dist/ 확인
```

---

## 기술 스택

| 레이어 | 사용 |
|---|---|
| Framework | Vue 3 (Composition API, `<script setup>`) |
| State | Pinia (setup function 문법) |
| Routing | Vue Router (JWT 가드) |
| HTTP | Axios (`src/api.js` 의 공용 인스턴스) |
| Build | Vite |
| Styling | 자체 디자인 시스템 (CSS 커스텀 속성 + 모듈 CSS) |

TypeScript / UI 라이브러리 / form validation 라이브러리는 **사용하지 않습니다.**
(Phase 3.4 에서 점진적 TS 전환을 고려)

---

## 디렉토리 레이아웃

```
frontend/
├── Dockerfile
├── nginx.conf                 # 운영용 nginx 설정 (정적 + /api/* 프록시)
├── entrypoint.sh
├── package.json
├── vite.config.js
└── src/
    ├── main.js                # 앱 부트스트랩
    ├── App.vue                # 루트 (글로벌 toast / modal)
    ├── api.js                 # Axios 인스턴스 + apiGet/Post/Put/Delete + downloadFile
    │
    ├── router/index.js        # 라우트 정의 + JWT 기반 가드
    │
    ├── layouts/
    │   └── MainLayout.vue     # Sidebar + Header + <RouterView/>
    │
    ├── views/                 # 얇은 쉘 — step 상태와 레이아웃만 소유
    │   ├── LoginView.vue
    │   ├── SignupView.vue
    │   ├── DashboardView.vue  # useTaskPolling 으로 queue 스냅샷 갱신
    │   ├── RTDView.vue        # 6단계 쉘 (~200줄)
    │   ├── EzDFSView.vue      # 4단계 쉘 (~200줄)
    │   ├── AdminView.vue      # 탭 쉘 (~60줄) — 4개 탭 위임
    │   └── MyPageView.vue
    │
    ├── components/
    │   ├── SidebarNav.vue
    │   ├── StatusBadge.vue
    │   ├── SvnResultModal.vue # RTD + ezDFS 공용 결과 모달
    │   ├── rtd/               # StepBusinessUnit, StepLine, StepRuleSelect,
    │   │                      #   StepMacroReview, StepTargetLine, StepExecute,
    │   │                      #   TargetMonitor, SvnUploadForm, monitorHelpers.js
    │   ├── ezdfs/             # StepModule, StepRuleSelect, StepSubRuleReview,
    │   │                      #   StepExecute, SvnUploadForm
    │   └── admin/             # UsersTab, HostsTab, RtdConfigsTab, EzdfsConfigsTab,
    │                          #   sortHelpers.js (sortItems + useSort 공유)
    │
    ├── composables/
    │   └── useTaskPolling.js  # onMounted/onBeforeUnmount 기반 폴링 훅
    │                          #   + waitForTaskTerminalStatus 대기 헬퍼
    │
    ├── stores/                # Pinia (setup function)
    │   ├── auth.js            # JWT / 사용자 정보 / localStorage 동기화
    │   ├── rtd.js             # RTD 위저드 상태 + 세션 저장/복원
    │   ├── ezdfs.js           # ezDFS 위저드 상태 + 세션 저장/복원
    │   ├── admin.js           # users / hosts / configs / ssh-limits 공용 저장소
    │   ├── ui.js              # 로딩 / 에러 / confirm 다이얼로그
    │   └── theme.js           # 라이트/다크 토글
    │
    ├── styles/                # 모듈화된 CSS (Phase 2.7)
    │   ├── tokens.css         # 색/스페이싱/타이포 CSS 커스텀 속성
    │   ├── base.css           # html/body 리셋, 타이포 기본값
    │   ├── layout.css         # 페이지 grid, shell
    │   ├── panels.css         # panel / card / article surface
    │   ├── forms.css          # input, select, button, field 스타일
    │   ├── components.css     # table, badge, modal, toast, tab
    │   ├── responsive.css     # 미디어쿼리
    │   └── pages/
    │       ├── dashboard.css
    │       ├── rtd.css
    │       ├── admin.css
    │       ├── monitor.css
    │       └── mypage.css
    └── style.css              # @import 만 있는 진입 파일 (21 줄)
```

---

## 상태 관리 모델

```
 ┌──────────────────────────────────────────────────────────┐
 │  views/*.vue  (thin shell)                               │
 │     · currentStep ref                                    │
 │     · selectionStats computed                            │
 │     · wizard 네비게이션                                  │
 └──────────────────┬───────────────────────────────────────┘
                    │ 자식 컴포넌트에 위임
                    ▼
 ┌──────────────────────────────────────────────────────────┐
 │  components/{rtd,ezdfs,admin}/*.vue                      │
 │     · UI / 사용자 입력 / 로컬 편집 draft                 │
 │     · useXxxStore() 로 공유 상태 접근                    │
 └──────────────────┬───────────────────────────────────────┘
                    │ reactive refs + actions
                    ▼
 ┌──────────────────────────────────────────────────────────┐
 │  stores/*.js  (Pinia setup function)                     │
 │     · API 호출 (api.js)                                  │
 │     · 서버 세션과 동기화                                 │
 │     · 전역 재사용 데이터 (hosts, users, configs …)       │
 └──────────────────────────────────────────────────────────┘
```

### 뷰-컴포넌트 경계 규칙
- `views/*.vue` 는 **step / tab 상태와 레이아웃만** 관리
- 실제 폼, 테이블, 상호작용은 `components/{rtd,ezdfs,admin}/` 으로 위임
- 뷰가 다시 1000줄짜리 컴포넌트로 커지지 않도록 주의 — 새 기능은
  기존 하위 컴포넌트에 붙이거나 새 컴포넌트를 추가해서 해결

### Pinia 스토어 범위
- `auth` / `ui` / `theme` — 전역 (모든 페이지 공통)
- `rtd` / `ezdfs` — 위저드 상태 + 서버 세션 싱크
- `admin` — admin 탭 4개가 공유하는 user / host / config 데이터

---

## 재사용 훅 (`composables/`)

### `useTaskPolling(tickFn, options?)`
```js
import { useTaskPolling } from '../composables/useTaskPolling'

useTaskPolling(() => store.refreshTasks(), { intervalMs: 3000 })
```
`onMounted` 에서 interval 을 걸고 `onBeforeUnmount` 에서 자동 해제.
직접 `setInterval` 을 호출하지 말고 이 훅을 사용합니다 (Phase 2.6).

### `waitForTaskTerminalStatus(...)`
`Execute all` 처럼 여러 task 가 전부 terminal 상태가 될 때까지
기다려야 할 때 사용. 타임아웃/폴링 간격을 옵션으로 조정 가능.

### `isTerminalTaskStatus(status)`
`DONE` / `FAIL` / `CANCELED` 체크용 유틸리티.

---

## 세션 복원

- 위저드 각 스텝이 바뀔 때마다 store 는 `/api/{rtd,ezdfs}/session` 에
  현재 상태를 PUT 합니다
- 페이지 새로고침 / 재로그인 시 `loadInitialData()` 가 저장된 세션을
  불러와 `currentStep`, 선택 값, 실행 상태를 복원합니다
- **이 흐름을 깨뜨리지 마세요** — 사용자가 수분간 쌓아온 선택이
  사라집니다. 스토어 변경 시 `saveSession()` 호출 위치 확인 필수.

---

## Admin 탭 공통 패턴

4개 탭 모두 동일한 편집 패턴을 따릅니다.

```
adminStore.loadAll()       ── mount 시 1회
    │
    ▼
storeToRefs(adminStore)    ── 각 탭이 필요한 리스트만 구독
    │
    ▼
reactive drafts            ── 로컬 편집 복사본 (inline 편집/cancel 용)
    │
    ▼
watch(source, syncDrafts,  ── loadAll 후 최신 데이터 반영
      { immediate: true })
    │
    ▼
adminStore.updateXxx(...)  ── 서버 변경 + loadAll() 재호출
```

정렬은 `components/admin/sortHelpers.js` 의 `useSort(defaultKey)` 를 써서
`sortKey`, `sortOrder`, `toggle`, `stateOf` 를 일관되게 제공합니다.

---

## API 호출 규약

```js
// src/api.js
import { apiGet, apiPost, apiPut, apiDelete, downloadFile } from '../api'

await apiGet('/api/admin/users')
await apiPost('/api/admin/hosts', payload)
await apiPut(`/api/admin/users/${id}`, payload)
await apiDelete(`/api/admin/users/${id}`)

await downloadFile('/api/mypage/rtd/raw/xxx')   // Content-Disposition 처리
```

- 401 은 axios interceptor 가 가로채서 `/login` 으로 리다이렉트
- 서버 에러 payload 는 `{ success: false, error: { code, message, detail } }`
  구조. `api.js` 가 표준 에러로 변환해서 store 가 `uiStore.setError()` 에
  전달합니다

---

## CSS 디자인 시스템

- CSS 커스텀 속성으로 라이트/다크 테마 지원
  - `:root { --color-... }` (라이트)
  - `[data-theme="dark"] { --color-... }` (다크)
- `styles/tokens.css` 하나만 바꾸면 전체 색/간격이 일괄 조정됨
- `style.css` 는 다음처럼 `@import` 만 포함하는 **엔트리 파일**:
  ```css
  @import './styles/tokens.css';
  @import './styles/base.css';
  @import './styles/layout.css';
  @import './styles/panels.css';
  @import './styles/forms.css';
  @import './styles/components.css';
  @import './styles/responsive.css';

  @import './styles/pages/dashboard.css';
  @import './styles/pages/rtd.css';
  @import './styles/pages/admin.css';
  @import './styles/pages/monitor.css';
  @import './styles/pages/mypage.css';
  ```
- 새 페이지 전용 스타일은 `styles/pages/` 아래에 파일을 추가하고
  `style.css` 에 import 한 줄 추가

---

## 코딩 컨벤션

- `<script setup>` + Composition API 만 사용 (Options API 금지)
- Pinia 스토어는 **setup function** 문법 (ref / reactive / computed)
- 모든 API 호출은 `api.js` 헬퍼를 경유 — 직접 `axios.get` 금지
- 파일 다운로드는 반드시 `downloadFile()` 사용 (Content-Disposition 처리)
- 폴링은 `useTaskPolling` 사용 (직접 `setInterval` 금지)
- UI 레이블은 **한국어 유지** — 임의로 번역/변경하지 않는다
- 컴포넌트 단일 책임 — 1개 파일이 500줄을 넘으면 분해 대상

---

## 흔한 작업 예시

### 새 스텝 컴포넌트 추가 (RTD 예)
1. `components/rtd/StepXxx.vue` 생성
2. `stores/rtd.js` 에 필요한 상태/액션 추가
3. `views/RTDView.vue` 의 step v-if 캐스케이드에 등록
4. 스텝 표시명과 카운트를 `steps` 배열에 추가

### 새 Admin 탭 추가
1. `components/admin/XxxTab.vue` 생성 (기존 탭 패턴 복붙)
2. `stores/admin.js` 에 해당 리소스 CRUD 액션 추가
3. `views/AdminView.vue` 의 탭 strip + v-if 캐스케이드에 등록

### 전역 테마 토큰 조정
1. `styles/tokens.css` 의 CSS 커스텀 속성만 수정
2. 필요 시 `[data-theme="dark"]` 섹션에 다크 값을 동시에 갱신

---

## 배포 (nginx)

운영 환경은 `npm run build` 결과물(`dist/`)을 nginx 로 서빙합니다
(`frontend/nginx.conf` 참조).

- 정적 자산: `dist/` 바로 서빙
- `/api/*` 요청: backend 컨테이너로 reverse-proxy
- SPA fallback: 모든 비 API 경로 → `index.html`

Docker build 는 루트 [README](../README.md) 의 배포 섹션 참고.

---

## 더 읽을거리

- [상위 README](../README.md) — 프로젝트 개요
- [`../CLAUDE.md`](../CLAUDE.md) — 전체 아키텍처 / 리팩토링 로드맵
- [`../docs/Front.md`](../docs/Front.md) — 디자인/구현 기준 (한글)
- [`../docs/plan.md`](../docs/plan.md) — 기획 요구사항 (한글)
