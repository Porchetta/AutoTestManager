<script setup>
import { onMounted, ref, computed } from "vue";
import { apiGet } from "../api";

const recentRtd = ref([]);
const recentEzdfs = ref([]);
const todayRtd = ref(0);
const todayEzdfs = ref(0);
const globalStats = ref(null);

const globalCharts = computed(() => {
  if (!globalStats.value) return [];
  return [
    { title: "RTD 일별",   ...globalStats.value.rtd_daily },
    { title: "RTD 월별",   ...globalStats.value.rtd_monthly },
    { title: "ezDFS 일별", ...globalStats.value.ezdfs_daily },
    { title: "ezDFS 월별", ...globalStats.value.ezdfs_monthly },
  ];
});

function maxOf(counts) {
  return Math.max(1, ...counts);
}

onMounted(async () => {
  try {
    recentRtd.value = (await apiGet("/api/mypage/rtd/recent")).items.slice(0, 3);
    recentEzdfs.value = (await apiGet("/api/mypage/ezdfs/recent")).items.slice(0, 3);
  } catch {
    recentRtd.value = [];
    recentEzdfs.value = [];
  }
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
  } catch {
    globalStats.value = null;
  }
});
</script>

<template>
  <section class="page-grid">
    <article class="hero-panel panel-span-2 dashboard-hero">
      <div class="dashboard-hero-copy">
        <p class="eyebrow">Operations Overview</p>
        <h2>RTD / ezDFS 테스트를 더욱 편하게</h2>
        <p>Test 실행부터 결과서 작성까지, One click Flow!</p>
        <div class="dashboard-hero-pills">
          <span class="pill">RTD Control</span>
          <span class="pill pill-ghost">Admin Console</span>
          <span class="pill pill-ghost">Session Restore</span>
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
        <div v-for="chart in globalCharts" :key="chart.title" class="stats-mini-chart">
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

    <article class="panel dashboard-feed-panel">
      <div class="panel-head">
        <h3>최근 RTD 작업</h3>
        <span class="pill pill-ghost">{{ recentRtd.length }}</span>
      </div>
      <div class="stack-list">
        <div
          v-for="item in recentRtd"
          :key="item.task_id"
          class="stack-item dashboard-feed-item"
        >
          <div>
            <strong>{{ item.target_name }}</strong>
            <p class="muted">{{ item.action_type }}</p>
          </div>
          <span class="pill pill-ghost">{{ item.status }}</span>
        </div>
        <p v-if="!recentRtd.length" class="muted">
          표시할 RTD 이력이 없습니다.
        </p>
      </div>
    </article>

    <article class="panel dashboard-feed-panel">
      <div class="panel-head">
        <h3>최근 ezDFS 작업</h3>
        <span class="pill pill-ghost">{{ recentEzdfs.length }}</span>
      </div>
      <div class="stack-list">
        <div
          v-for="item in recentEzdfs"
          :key="item.task_id"
          class="stack-item dashboard-feed-item"
        >
          <div>
            <strong>{{ item.target_name }}</strong>
            <p class="muted">{{ item.action_type }}</p>
          </div>
          <span class="pill pill-ghost">{{ item.status }}</span>
        </div>
        <p v-if="!recentEzdfs.length" class="muted">
          표시할 ezDFS 이력이 없습니다.
        </p>
      </div>
    </article>
  </section>
</template>
