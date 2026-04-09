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
    <article class="hero-panel">
      <p class="eyebrow">Operations Overview</p>
      <h2>RTD / ezDFS 흐름을 끊김 없이 추적</h2>
      <p>
        설정, 실행, 상태 확인, 결과 다운로드를 각각 분리하지 않고 하나의 콘솔 안에서 이어지게
        구성했습니다.
      </p>
    </article>

    <article class="metric-card">
      <span class="metric-label">RTD Recent</span>
      <strong class="metric-value">{{ recentRtd.length }}</strong>
      <p>최근 RTD 작업 카드 수</p>
    </article>

    <article class="metric-card">
      <span class="metric-label">ezDFS Recent</span>
      <strong class="metric-value">{{ recentEzdfs.length }}</strong>
      <p>최근 ezDFS 작업 카드 수</p>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>최근 RTD 작업</h3>
      </div>
      <div class="stack-list">
        <div v-for="item in recentRtd" :key="item.task_id" class="stack-item">
          <strong>{{ item.target_name }}</strong>
          <span>{{ item.status }}</span>
        </div>
        <p v-if="!recentRtd.length" class="muted">표시할 RTD 이력이 없습니다.</p>
      </div>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>최근 ezDFS 작업</h3>
      </div>
      <div class="stack-list">
        <div v-for="item in recentEzdfs" :key="item.task_id" class="stack-item">
          <strong>{{ item.target_name }}</strong>
          <span>{{ item.status }}</span>
        </div>
        <p v-if="!recentEzdfs.length" class="muted">표시할 ezDFS 이력이 없습니다.</p>
      </div>
    </article>
  </section>
</template>

