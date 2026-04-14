<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import { apiGet, apiPost } from "../api";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const todayRtd = ref(0);
const todayEzdfs = ref(0);
const globalStats = ref(null);
const currentQueue = ref([]);
const heroLiked = ref(false);
const dashboardLikeCount = ref(0);
const DASHBOARD_QUEUE_REFRESH_MS = 3000;
let queueRefreshTimer = null;

const globalCharts = computed(() => {
  if (!globalStats.value) return [];
  return [
    { title: "RTD 일별", ...globalStats.value.rtd_daily },
    { title: "RTD 월별", ...globalStats.value.rtd_monthly },
    { title: "ezDFS 일별", ...globalStats.value.ezdfs_daily },
    { title: "ezDFS 월별", ...globalStats.value.ezdfs_monthly },
  ];
});

const rtdQueue = computed(() =>
  currentQueue.value.filter((item) => item.test_type === "RTD"),
);

const ezdfsQueue = computed(() =>
  currentQueue.value.filter((item) => item.test_type === "EZDFS"),
);

function maxOf(counts) {
  return Math.max(1, ...counts);
}

function queueTargetLabel(item) {
  return item.queue_title || item.target_name;
}

async function loadDashboardLike() {
  const data = await apiGet("/api/mypage/dashboard/like");
  heroLiked.value = Boolean(data.liked);
  dashboardLikeCount.value = Number(data.count || 0);
}

async function toggleHeroLike() {
  const data = await apiPost("/api/mypage/dashboard/like/toggle");
  heroLiked.value = Boolean(data.liked);
  dashboardLikeCount.value = Number(data.count || 0);
}

async function loadCurrentQueue() {
  currentQueue.value =
    (await apiGet("/api/mypage/dashboard/queue")).items || [];
}

onMounted(async () => {
  try {
    const today = await apiGet("/api/mypage/stats/today");
    todayRtd.value = today.rtd;
    todayEzdfs.value = today.ezdfs;
  } catch {
    todayRtd.value = 0;
    todayEzdfs.value = 0;
  }
  try {
    globalStats.value = await apiGet("/api/mypage/stats/global");
    dashboardLikeCount.value = Number(
      globalStats.value?.dashboard_like_count || 0,
    );
  } catch {
    globalStats.value = null;
    dashboardLikeCount.value = 0;
  }
  try {
    await loadCurrentQueue();
  } catch {
    currentQueue.value = [];
  }
  try {
    await loadDashboardLike();
  } catch {
    heroLiked.value = false;
  }

  queueRefreshTimer = window.setInterval(async () => {
    try {
      await loadCurrentQueue();
    } catch {
      // Keep the last visible queue state when a background refresh fails.
    }
  }, DASHBOARD_QUEUE_REFRESH_MS);
});

onBeforeUnmount(() => {
  if (queueRefreshTimer) {
    window.clearInterval(queueRefreshTimer);
    queueRefreshTimer = null;
  }
});
</script>

<template>
  <section class="page-grid">
    <article class="hero-panel panel-span-2 dashboard-hero">
      <div class="dashboard-hero-copy">
        <p class="eyebrow">Operations Overview</p>
        <h2>RTD / ezDFS 테스트를 더욱 편하게</h2>
        <p>One-click testing, made easy.</p>
        <div class="dashboard-hero-pills">
          <span class="pill">#RTDTest</span>
          <span class="pill">#ezDFSTest</span>
          <span class="pill pill-ghost">#MSS</span>
          <button
            class="dashboard-like-button"
            :class="{ 'is-active': heroLiked }"
            type="button"
            :aria-pressed="heroLiked"
            @click="toggleHeroLike"
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M10 17s-5.5-3.45-7.35-6.48C1.3 8.28 1.8 5.2 4.54 4.17c1.8-.67 3.42.05 4.46 1.36 1.04-1.31 2.66-2.03 4.46-1.36 2.74 1.03 3.24 4.11 1.89 6.35C15.5 13.55 10 17 10 17Z"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span>{{ heroLiked ? "Liked" : "Like" }}</span>
            <strong>{{ dashboardLikeCount }}</strong>
          </button>
        </div>
      </div>
      <div class="dashboard-summary-rail">
        <div class="dashboard-summary-tile">
          <span class="metric-label">RTD Recent</span>
          <strong>{{ todayRtd }}</strong>
          <p>Today RTD Test Count</p>
        </div>
        <div class="dashboard-summary-tile">
          <span class="metric-label">ezDFS Recent</span>
          <strong>{{ todayEzdfs }}</strong>
          <p>Today ezDFS Test Count</p>
        </div>
      </div>
    </article>

    <article class="panel panel-span-2 dashboard-overview-console">
      <div class="panel-head">
        <h3>User Usage History</h3>
        <span class="pill pill-ghost">Live Surface</span>
      </div>
      <div v-if="globalStats" class="stats-mini-grid dashboard-stats-grid">
        <div
          v-for="chart in globalCharts"
          :key="chart.title"
          class="stats-mini-chart"
        >
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

    <article class="panel dashboard-queue-panel">
      <div class="panel-head">
        <h3>Current RTD Queue</h3>
        <span class="pill pill-ghost">{{ rtdQueue.length }}</span>
      </div>
      <div class="dashboard-queue-list">
        <div
          v-for="item in rtdQueue"
          :key="item.task_id"
          class="dashboard-queue-card"
        >
          <div class="dashboard-queue-copy">
            <strong>{{ queueTargetLabel(item) }}</strong>
            <p class="muted">
              {{ item.queue_meta }}
            </p>
          </div>
          <span class="status-badge" :data-status="item.status">{{
            item.status
          }}</span>
        </div>
        <p v-if="!rtdQueue.length" class="muted">
          현재 대기 중이거나 실행 중인 RTD 작업이 없습니다.
        </p>
      </div>
    </article>

    <article class="panel dashboard-queue-panel">
      <div class="panel-head">
        <h3>Current ezDFS Queue</h3>
        <span class="pill pill-ghost">{{ ezdfsQueue.length }}</span>
      </div>
      <div class="dashboard-queue-list">
        <div
          v-for="item in ezdfsQueue"
          :key="item.task_id"
          class="dashboard-queue-card"
        >
          <div class="dashboard-queue-copy">
            <strong>{{ queueTargetLabel(item) }}</strong>
            <p class="muted">
              {{ item.queue_meta }}
            </p>
          </div>
          <span class="status-badge" :data-status="item.status">{{
            item.status
          }}</span>
        </div>
        <p v-if="!ezdfsQueue.length" class="muted">
          현재 대기 중이거나 실행 중인 ezDFS 작업이 없습니다.
        </p>
      </div>
    </article>
  </section>
</template>
