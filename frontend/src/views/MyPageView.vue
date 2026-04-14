<script setup>
import { onMounted, reactive, ref, computed, watch } from "vue";
import { apiGet, downloadFile } from "../api";
import StatusBadge from "../components/StatusBadge.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const authStore = useAuthStore();
const uiStore = useUiStore();

const passwordModalOpen = ref(false);
const passwordSaving = ref(false);
const passwordForm = reactive({ new_password: "" });

// ── Stats ──────────────────────────────────────────────────────────────────
const statsData = ref(null);

const miniCharts = computed(() => {
  if (!statsData.value) return [];
  return [
    { title: "RTD 일별",   ...statsData.value.rtd_daily },
    { title: "RTD 월별",   ...statsData.value.rtd_monthly },
    { title: "ezDFS 일별", ...statsData.value.ezdfs_daily },
    { title: "ezDFS 월별", ...statsData.value.ezdfs_monthly },
  ];
});

function maxOf(counts) {
  return Math.max(1, ...counts);
}

async function loadStats() {
  statsData.value = await apiGet("/api/mypage/stats");
}

// ── Result panels ──────────────────────────────────────────────────────────
const rtdRaw = reactive({ line: "", rule: "", page: 1, items: [], total: 0, pages: 1, loading: false, lineOptions: [], ruleOptions: [] });
const rtdReport = reactive({ page: 1, items: [], total: 0, pages: 1, loading: false });
const ezdfsRaw = reactive({ page: 1, items: [], total: 0, pages: 1, loading: false });
const ezdfsReport = reactive({ page: 1, items: [], total: 0, pages: 1, loading: false });

async function loadRtdRawOptions() {
  const r = await apiGet("/api/mypage/rtd/results/raw/options");
  rtdRaw.lineOptions = r.lines;
  rtdRaw.ruleOptions = r.rules;
}

async function loadRtdRaw() {
  rtdRaw.loading = true;
  try {
    const p = new URLSearchParams({ page: rtdRaw.page });
    if (rtdRaw.line) p.set("line", rtdRaw.line);
    if (rtdRaw.rule) p.set("rule", rtdRaw.rule);
    const r = await apiGet(`/api/mypage/rtd/results/raw?${p}`);
    Object.assign(rtdRaw, r);
  } finally {
    rtdRaw.loading = false;
  }
}

async function loadRtdReport() {
  rtdReport.loading = true;
  try {
    const r = await apiGet(`/api/mypage/rtd/results/summary?page=${rtdReport.page}`);
    Object.assign(rtdReport, r);
  } finally {
    rtdReport.loading = false;
  }
}

async function loadEzdfsRaw() {
  ezdfsRaw.loading = true;
  try {
    const r = await apiGet(`/api/mypage/ezdfs/results/raw?page=${ezdfsRaw.page}`);
    Object.assign(ezdfsRaw, r);
  } finally {
    ezdfsRaw.loading = false;
  }
}

async function loadEzdfsReport() {
  ezdfsReport.loading = true;
  try {
    const r = await apiGet(`/api/mypage/ezdfs/results/summary?page=${ezdfsReport.page}`);
    Object.assign(ezdfsReport, r);
  } finally {
    ezdfsReport.loading = false;
  }
}

function resetAndLoad(panel, loadFn) {
  panel.page = 1;
  loadFn();
}

watch([() => rtdRaw.line, () => rtdRaw.rule], () => resetAndLoad(rtdRaw, loadRtdRaw));

onMounted(() => {
  loadStats();
  loadRtdRawOptions();
  loadRtdRaw();
  loadRtdReport();
  loadEzdfsRaw();
  loadEzdfsReport();
});

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  const ho = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mo}/${da} ${ho}:${mi}`;
}

function openPasswordModal() {
  passwordForm.new_password = "";
  passwordModalOpen.value = true;
}
function closePasswordModal() {
  passwordModalOpen.value = false;
  passwordForm.new_password = "";
}
async function changePassword() {
  passwordSaving.value = true;
  try {
    await authStore.changePassword({ new_password: passwordForm.new_password });
    closePasswordModal();
    uiStore.setNotice("비밀번호가 변경되었습니다.");
  } finally {
    passwordSaving.value = false;
  }
}

async function dlRaw(item, testType) {
  const params = new URLSearchParams({ kind: "raw" });
  if (testType === "RTD" && item?.rule) {
    params.set("rule", item.rule);
  }
  await downloadFile(`/api/mypage/results/${item.task_id}/download?${params.toString()}`, `raw_${item.task_id}`);
}
async function dlSummary(taskId) {
  await downloadFile(`/api/mypage/results/${taskId}/download?kind=summary`, `report_${taskId}`);
}
</script>

<template>
  <section class="page-grid mypage-grid">
    <!-- 계정 정보 -->
    <article class="panel">
      <div class="panel-head">
        <div>
          <h3>내 계정 정보</h3>
          <p class="muted">현재 로그인한 계정 정보입니다.</p>
        </div>
        <button class="button button-primary" type="button" @click="openPasswordModal">
          비밀번호 변경
        </button>
      </div>
      <div class="mypage-account-stats">
        <div class="mini-stat">
          <span>User ID</span>
          <strong>{{ authStore.user?.user_id }}</strong>
        </div>
        <div class="mini-stat">
          <span>Name</span>
          <strong>{{ authStore.user?.user_name }}</strong>
        </div>
        <div class="mini-stat">
          <span>Module</span>
          <strong>{{ authStore.user?.module_name }}</strong>
        </div>
        <div class="mini-stat">
          <span>Role</span>
          <strong>{{ authStore.isAdmin ? "Admin" : "User" }}</strong>
        </div>
      </div>
    </article>

    <!-- Test History -->
    <article class="panel stats-panel">
      <div class="panel-head stats-panel-head">
        <h3>Test History</h3>
      </div>
      <div v-if="statsData" class="stats-mini-grid">
        <div v-for="chart in miniCharts" :key="chart.title" class="stats-mini-chart">
          <div class="stats-mini-title">{{ chart.title }}</div>
          <div class="stats-mini-bars">
            <div
              v-for="(cnt, i) in chart.counts"
              :key="i"
              class="stats-mini-bar"
              :style="{ height: (cnt / maxOf(chart.counts)) * 100 + '%' }"
              :title="`${chart.labels[i]}: ${cnt}회`"
            ></div>
          </div>
          <div class="stats-mini-foot">
            <span>{{ chart.labels[0] }}</span>
            <span>{{ chart.labels[chart.labels.length - 1] }}</span>
          </div>
        </div>
      </div>
      <div v-else class="muted stats-loading">불러오는 중...</div>
    </article>

    <!-- 4개 다운로드 패널 -->
    <div class="panel-span-2 result-panels-row">

      <!-- RTD Test Raw Data -->
      <article class="panel result-panel">
        <div class="panel-head result-panel-head">
          <h3>RTD Test Raw Data</h3>
        </div>
        <div class="result-filters">
          <select v-model="rtdRaw.line" class="result-select">
            <option value="">전체 Line</option>
            <option v-for="l in rtdRaw.lineOptions" :key="l" :value="l">{{ l }}</option>
          </select>
          <select v-model="rtdRaw.rule" class="result-select">
            <option value="">전체 Rule</option>
            <option v-for="r in rtdRaw.ruleOptions" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div class="result-list">
          <div v-if="rtdRaw.loading" class="result-empty muted">불러오는 중...</div>
          <template v-else-if="rtdRaw.items.length">
            <div v-for="item in rtdRaw.items" :key="item.task_id" class="result-item">
              <span class="result-label">
                <span class="result-tag">{{ item.line }}</span>
                <span class="result-tag">{{ item.rule }}</span>
                <span class="result-time">{{ fmtTime(item.requested_at) }}</span>
              </span>
              <button class="result-dl-btn" title="다운로드" @click="dlRaw(item, 'RTD')">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
              </button>
            </div>
          </template>
          <div v-else class="result-empty muted">이력이 없습니다.</div>
        </div>
        <div class="result-pagination">
          <button class="result-page-btn" :disabled="rtdRaw.page <= 1" @click="rtdRaw.page--; loadRtdRaw()">‹</button>
          <span>{{ rtdRaw.page }} / {{ rtdRaw.pages }}</span>
          <button class="result-page-btn" :disabled="rtdRaw.page >= rtdRaw.pages" @click="rtdRaw.page++; loadRtdRaw()">›</button>
        </div>
      </article>

      <!-- RTD Test Report -->
      <article class="panel result-panel">
        <div class="panel-head result-panel-head">
          <h3>RTD Test Report</h3>
        </div>
        <div class="result-list">
          <div v-if="rtdReport.loading" class="result-empty muted">불러오는 중...</div>
          <template v-else-if="rtdReport.items.length">
            <div v-for="item in rtdReport.items" :key="item.task_id" class="result-item">
              <span class="result-label">
                <span class="result-tag">{{ item.business_unit }}</span>
                <span class="result-time">{{ fmtTime(item.requested_at) }}</span>
              </span>
              <button class="result-dl-btn" title="다운로드" @click="dlSummary(item.task_id)">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
              </button>
            </div>
          </template>
          <div v-else class="result-empty muted">이력이 없습니다.</div>
        </div>
        <div class="result-pagination">
          <button class="result-page-btn" :disabled="rtdReport.page <= 1" @click="rtdReport.page--; loadRtdReport()">‹</button>
          <span>{{ rtdReport.page }} / {{ rtdReport.pages }}</span>
          <button class="result-page-btn" :disabled="rtdReport.page >= rtdReport.pages" @click="rtdReport.page++; loadRtdReport()">›</button>
        </div>
      </article>

      <!-- ezDFS Test Raw Data -->
      <article class="panel result-panel">
        <div class="panel-head result-panel-head">
          <h3>ezDFS Test Raw Data</h3>
        </div>
        <div class="result-list">
          <div v-if="ezdfsRaw.loading" class="result-empty muted">불러오는 중...</div>
          <template v-else-if="ezdfsRaw.items.length">
            <div v-for="item in ezdfsRaw.items" :key="item.task_id" class="result-item">
              <span class="result-label">
                <span class="result-tag">{{ item.rule }}</span>
                <span class="result-time">{{ fmtTime(item.requested_at) }}</span>
              </span>
              <button class="result-dl-btn" title="다운로드" @click="dlRaw(item, 'EZDFS')">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
              </button>
            </div>
          </template>
          <div v-else class="result-empty muted">이력이 없습니다.</div>
        </div>
        <div class="result-pagination">
          <button class="result-page-btn" :disabled="ezdfsRaw.page <= 1" @click="ezdfsRaw.page--; loadEzdfsRaw()">‹</button>
          <span>{{ ezdfsRaw.page }} / {{ ezdfsRaw.pages }}</span>
          <button class="result-page-btn" :disabled="ezdfsRaw.page >= ezdfsRaw.pages" @click="ezdfsRaw.page++; loadEzdfsRaw()">›</button>
        </div>
      </article>

      <!-- ezDFS Test Report -->
      <article class="panel result-panel">
        <div class="panel-head result-panel-head">
          <h3>ezDFS Test Report</h3>
        </div>
        <div class="result-list">
          <div v-if="ezdfsReport.loading" class="result-empty muted">불러오는 중...</div>
          <template v-else-if="ezdfsReport.items.length">
            <div v-for="item in ezdfsReport.items" :key="item.task_id" class="result-item">
              <span class="result-label">
                <span class="result-tag">{{ item.module }}</span>
                <span class="result-time">{{ fmtTime(item.requested_at) }}</span>
              </span>
              <button class="result-dl-btn" title="다운로드" @click="dlSummary(item.task_id)">
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
              </button>
            </div>
          </template>
          <div v-else class="result-empty muted">이력이 없습니다.</div>
        </div>
        <div class="result-pagination">
          <button class="result-page-btn" :disabled="ezdfsReport.page <= 1" @click="ezdfsReport.page--; loadEzdfsReport()">‹</button>
          <span>{{ ezdfsReport.page }} / {{ ezdfsReport.pages }}</span>
          <button class="result-page-btn" :disabled="ezdfsReport.page >= ezdfsReport.pages" @click="ezdfsReport.page++; loadEzdfsReport()">›</button>
        </div>
      </article>

    </div>
  </section>

  <div v-if="passwordModalOpen" class="modal-overlay" @click.self="closePasswordModal">
    <div class="confirm-modal password-modal">
      <h3>비밀번호 변경</h3>
      <p class="confirm-copy">새 비밀번호를 입력하면 현재 계정 비밀번호가 즉시 변경됩니다.</p>
      <form class="stack-form password-modal-form" @submit.prevent="changePassword">
        <label class="field">
          <span>New Password</span>
          <input v-model="passwordForm.new_password" type="password" minlength="4" autofocus />
        </label>
        <div class="confirm-actions">
          <button class="button button-ghost" type="button" @click="closePasswordModal">취소</button>
          <button class="button button-primary" type="submit" :disabled="passwordSaving || !passwordForm.new_password">
            {{ passwordSaving ? "변경중" : "변경" }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
