<script setup>
import { onMounted, reactive, ref } from 'vue'
import { apiGet, downloadFile } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

const authStore = useAuthStore()
const uiStore = useUiStore()

const passwordModalOpen = ref(false)
const passwordSaving = ref(false)
const passwordForm = reactive({
  new_password: '',
})

const recentRtd = ref([])
const recentEzdfs = ref([])

async function loadRecent() {
  recentRtd.value = (await apiGet('/api/mypage/rtd/recent')).items
  recentEzdfs.value = (await apiGet('/api/mypage/ezdfs/recent')).items
}

onMounted(loadRecent)

function openPasswordModal() {
  passwordForm.new_password = ''
  passwordModalOpen.value = true
}

function closePasswordModal() {
  passwordModalOpen.value = false
  passwordForm.new_password = ''
}

async function changePassword() {
  passwordSaving.value = true
  try {
    await authStore.changePassword({
      new_password: passwordForm.new_password,
    })
    closePasswordModal()
    uiStore.setNotice('비밀번호가 변경되었습니다.')
  } finally {
    passwordSaving.value = false
  }
}

async function downloadResult(taskId) {
  await downloadFile(`/api/mypage/results/${taskId}/download`, `result_${taskId}`)
}
</script>

<template>
  <section class="page-grid">
    <article class="panel panel-span-2">
      <div class="panel-head">
        <div>
          <h3>내 계정 정보</h3>
          <p class="muted">현재 로그인한 계정 정보와 최근 테스트 이력을 확인할 수 있습니다.</p>
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
          <strong>{{ authStore.isAdmin ? 'Admin' : 'User' }}</strong>
        </div>
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
            {{ passwordSaving ? '변경중' : '변경' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
