<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUiStore()

const form = reactive({
  user_id: '',
  user_name: '',
  password: '',
  confirm_password: '',
  module_name: '',
})

async function handleSubmit() {
  if (form.password !== form.confirm_password) {
    uiStore.setError('비밀번호 확인이 일치하지 않습니다.')
    return
  }

  await authStore.signup({
    user_id: form.user_id,
    user_name: form.user_name,
    password: form.password,
    module_name: form.module_name,
  })
  uiStore.setNotice('회원가입 요청이 접수되었습니다. 관리자 승인을 기다려주세요.')
  router.push('/login')
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-hero">
      <p class="eyebrow">Access Request</p>
      <h1>운영 콘솔 접근 요청</h1>
      <p>가입 후 관리자의 승인 절차를 거쳐 로그인할 수 있습니다.</p>
    </div>

    <form class="auth-card auth-card-wide" @submit.prevent="handleSubmit">
      <h2>Sign Up</h2>
      <div class="field-grid">
        <label class="field">
          <span>User ID</span>
          <input v-model="form.user_id" />
        </label>
        <label class="field">
          <span>User Name</span>
          <input v-model="form.user_name" />
        </label>
        <label class="field">
          <span>Password</span>
          <input v-model="form.password" type="password" />
        </label>
        <label class="field">
          <span>Confirm Password</span>
          <input v-model="form.confirm_password" type="password" />
        </label>
        <label class="field field-span-2">
          <span>Module Name</span>
          <input v-model="form.module_name" />
        </label>
      </div>
      <button class="button button-primary" type="submit">가입 요청</button>
      <RouterLink class="text-link" to="/login">로그인으로 돌아가기</RouterLink>
    </form>
  </div>
</template>

