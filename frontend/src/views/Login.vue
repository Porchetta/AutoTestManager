<template>
  <div class="login-container">
    <div class="glass-panel login-box">
      <h2>MSS Test Manager</h2>
      <form @submit.prevent="handleLogin">
        <div class="input-group">
          <label>Username</label>
          <input v-model="username" type="text" required />
        </div>
        <div class="input-group">
          <label>Password</label>
          <input v-model="password" type="password" required />
        </div>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

const handleLogin = async () => {
  loading.value = true;
  error.value = '';
  try {
    await authStore.login(username.value, password.value);
  } catch (err) {
    error.value = 'Invalid credentials or not approved.';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: radial-gradient(circle at top left, #2a2a2a, #000);
}
.login-box {
  padding: 3rem;
  width: 350px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  text-align: center;
}
.input-group {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 0.5rem;
}
input {
  padding: 0.8rem;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(0,0,0,0.3);
  color: white;
  font-size: 1rem;
}
input:focus {
  outline: none;
  border-color: var(--primary-color);
}
.error-msg {
  color: #ff6b6b;
  font-size: 0.9rem;
}
</style>
