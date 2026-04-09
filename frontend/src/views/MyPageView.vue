<script setup>
import { onMounted, reactive, ref } from 'vue'
import { apiGet, downloadFile } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

const authStore = useAuthStore()
const uiStore = useUiStore()

const passwordForm = reactive({
  current_password: '',
  new_password: '',
})

const recentRtd = ref([])
const recentEzdfs = ref([])

async function loadRecent() {
  recentRtd.value = (await apiGet('/api/mypage/rtd/recent')).items
  recentEzdfs.value = (await apiGet('/api/mypage/ezdfs/recent')).items
}

onMounted(loadRecent)

async function changePassword() {
  await authStore.changePassword(passwordForm)
  passwordForm.current_password = ''
  passwordForm.new_password = ''
  uiStore.setNotice('비밀번호가 변경되었습니다.')
}

async function downloadResult(taskId) {
  await downloadFile(`/api/mypage/results/${taskId}/download`, `result_${taskId}`)
}
</script>

<template>
  <section class="page-grid">
    <article class="panel">
      <div class="panel-head">
        <h3>비밀번호 변경</h3>
      </div>
      <form class="stack-form" @submit.prevent="changePassword">
        <label class="field">
          <span>Current Password</span>
          <input v-model="passwordForm.current_password" type="password" />
        </label>
        <label class="field">
          <span>New Password</span>
          <input v-model="passwordForm.new_password" type="password" />
        </label>
        <button class="button button-primary" type="submit">변경</button>
      </form>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>내 계정 정보</h3>
      </div>
      <div class="stack-list">
        <div class="stack-item"><strong>User ID</strong><span>{{ authStore.user?.user_id }}</span></div>
        <div class="stack-item"><strong>Name</strong><span>{{ authStore.user?.user_name }}</span></div>
        <div class="stack-item"><strong>Module</strong><span>{{ authStore.user?.module_name }}</span></div>
        <div class="stack-item"><strong>Role</strong><span>{{ authStore.isAdmin ? 'Admin' : 'User' }}</span></div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>최근 RTD 결과</h3>
      </div>
      <div class="task-grid compact-grid">
        <div v-for="task in recentRtd" :key="task.task_id" class="task-card">
          <div class="task-head">
            <strong>{{ task.target_name }}</strong>
            <StatusBadge :status="task.status" />
          </div>
          <button class="button button-ghost" @click="downloadResult(task.task_id)">다운로드</button>
        </div>
        <p v-if="!recentRtd.length" class="muted">RTD 이력이 없습니다.</p>
      </div>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>최근 ezDFS 결과</h3>
      </div>
      <div class="task-grid compact-grid">
        <div v-for="task in recentEzdfs" :key="task.task_id" class="task-card">
          <div class="task-head">
            <strong>{{ task.target_name }}</strong>
            <StatusBadge :status="task.status" />
          </div>
          <button class="button button-ghost" @click="downloadResult(task.task_id)">다운로드</button>
        </div>
        <p v-if="!recentEzdfs.length" class="muted">ezDFS 이력이 없습니다.</p>
      </div>
    </article>
  </section>
</template>

