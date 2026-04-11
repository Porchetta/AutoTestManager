<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const authStore = useAuthStore();

const form = reactive({
  user_id: "",
  password: "",
});

async function handleSubmit() {
  await authStore.login(form);
  router.push("/");
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-hero">
      <p class="eyebrow">for MSS</p>
      <h1>Auto Test Manager</h1>
      <p>안녕하세요, 좋은 아침입니다 :)</p>
    </div>

    <form class="auth-card" @submit.prevent="handleSubmit">
      <h2>Login</h2>
      <label class="field">
        <span>User ID</span>
        <input v-model="form.user_id" placeholder="아이디를 입력해주세요" />
      </label>
      <label class="field">
        <span>Password</span>
        <input
          v-model="form.password"
          type="password"
          placeholder="비밀번호를 입력해주세요"
        />
      </label>
      <button class="button button-primary" type="submit">로그인</button>
      <RouterLink class="text-link" to="/signup">회원가입 요청하기</RouterLink>
    </form>
  </div>
</template>
