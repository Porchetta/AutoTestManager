<script setup>
import { onMounted, ref } from 'vue'
import { apiGet } from '../api'

const recentRtd = ref([])
const recentEzdfs = ref([])

onMounted(async () => {
  try {
    recentRtd.value = (await apiGet('/api/mypage/rtd/recent')).items.slice(0, 3)
    recentEzdfs.value = (await apiGet('/api/mypage/ezdfs/recent')).items.slice(0, 3)
  } catch {
    recentRtd.value = []
    recentEzdfs.value = []
  }
})
</script>

<template>
  <section class="page-grid">
    <article class="hero-panel panel-span-2 dashboard-hero">
      <div class="dashboard-hero-copy">
        <p class="eyebrow">Operations Overview</p>
        <h2>RTD / ezDFS 흐름을 끊김 없이 추적</h2>
        <p>
          설정, 실행, 상태 확인, 결과 다운로드를 각각 분리하지 않고 하나의 콘솔 안에서 이어지게
          구성했습니다.
        </p>
        <div class="dashboard-hero-pills">
          <span class="pill">RTD Control</span>
          <span class="pill pill-ghost">Admin Console</span>
          <span class="pill pill-ghost">Session Restore</span>
        </div>
      </div>
      <div class="dashboard-summary-rail">
        <div class="dashboard-summary-tile">
          <span class="metric-label">RTD Recent</span>
          <strong>{{ recentRtd.length }}</strong>
          <p>최근 RTD 작업 카드 수</p>
        </div>
        <div class="dashboard-summary-tile">
          <span class="metric-label">ezDFS Recent</span>
          <strong>{{ recentEzdfs.length }}</strong>
          <p>최근 ezDFS 작업 카드 수</p>
        </div>
      </div>
    </article>

    <article class="panel panel-span-2 dashboard-overview-console">
      <div class="panel-head">
        <h3>Overview Console</h3>
        <span class="pill pill-ghost">Live Surface</span>
      </div>
      <div class="dashboard-console-grid">
        <div class="dashboard-console-item">
          <span class="metric-label">RTD</span>
          <strong>{{ recentRtd.length }}</strong>
          <p>Rule 선택, Macro 확인, 타겟 실행 제어를 한 흐름으로 다룹니다.</p>
        </div>
        <div class="dashboard-console-item">
          <span class="metric-label">ezDFS</span>
          <strong>{{ recentEzdfs.length }}</strong>
          <p>모듈 기준 테스트, 재테스트, 결과서 생성을 단일 흐름으로 제공합니다.</p>
        </div>
        <div class="dashboard-console-item">
          <span class="metric-label">Admin</span>
          <strong>4</strong>
          <p>Users, Hosts, RTD, ezDFS 설정을 같은 콘솔 규칙으로 관리합니다.</p>
        </div>
      </div>
    </article>

    <article class="panel dashboard-feed-panel">
      <div class="panel-head">
        <h3>최근 RTD 작업</h3>
        <span class="pill pill-ghost">{{ recentRtd.length }}</span>
      </div>
      <div class="stack-list">
        <div v-for="item in recentRtd" :key="item.task_id" class="stack-item dashboard-feed-item">
          <div>
            <strong>{{ item.target_name }}</strong>
            <p class="muted">{{ item.action_type }}</p>
          </div>
          <span class="pill pill-ghost">{{ item.status }}</span>
        </div>
        <p v-if="!recentRtd.length" class="muted">표시할 RTD 이력이 없습니다.</p>
      </div>
    </article>

    <article class="panel dashboard-feed-panel">
      <div class="panel-head">
        <h3>최근 ezDFS 작업</h3>
        <span class="pill pill-ghost">{{ recentEzdfs.length }}</span>
      </div>
      <div class="stack-list">
        <div v-for="item in recentEzdfs" :key="item.task_id" class="stack-item dashboard-feed-item">
          <div>
            <strong>{{ item.target_name }}</strong>
            <p class="muted">{{ item.action_type }}</p>
          </div>
          <span class="pill pill-ghost">{{ item.status }}</span>
        </div>
        <p v-if="!recentEzdfs.length" class="muted">표시할 ezDFS 이력이 없습니다.</p>
      </div>
    </article>
  </section>
</template>
