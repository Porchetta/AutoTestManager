<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  user_id: '',
  password: '',
})

async function handleSubmit() {
  await authStore.login(form)
  router.push('/')
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-hero">
      <p class="eyebrow">Night Shift Console</p>
      <h1>테스트 운영을 더 빠르고 또렷하게</h1>
      <p>
        복사, 컴파일, 테스트, 결과서 다운로드까지 한 흐름으로 묶어주는 다크 테마 운영 화면입니다.
      </p>
    </div>

    <form class="auth-card" @submit.prevent="handleSubmit">
      <h2>Login</h2>
      <label class="field">
        <span>User ID</span>
        <input v-model="form.user_id" placeholder="admin" />
      </label>
      <label class="field">
        <span>Password</span>
        <input v-model="form.password" type="password" placeholder="admin1234" />
      </label>
      <button class="button button-primary" type="submit">로그인</button>
      <RouterLink class="text-link" to="/signup">회원가입 요청하기</RouterLink>
    </form>
  </div>
</template>

