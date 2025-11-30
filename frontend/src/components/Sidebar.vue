<template>
  <aside class="sidebar glass-panel">
    <div class="logo">
      <h3>MSS Manager</h3>
    </div>
    <nav>
      <router-link to="/" class="nav-item" active-class="active">
        <span>🏠 Dashboard</span>
      </router-link>
      <router-link to="/rtd" class="nav-item" active-class="active">
        <span>📝 RTD Test</span>
      </router-link>
      <router-link to="/ezdfs" class="nav-item" active-class="active">
        <span>🎯 ezDFS Test</span>
      </router-link>
      <router-link to="/mypage" class="nav-item" active-class="active">
        <span>🧑‍💻 My Page</span>
      </router-link>
      <router-link to="/admin" class="nav-item" active-class="active">
        <span>👑 Admin</span>
      </router-link>
    </nav>
    <div class="footer">
      <button @click="authStore.logout()" class="logout-btn">Logout</button>
    </div>
  </aside>
</template>

<script setup>
import { useAuthStore } from '../stores/auth';
const authStore = useAuthStore();
</script>

<style scoped>
.sidebar {
  width: 250px;
  height: 95vh;
  margin: 2.5vh;
  display: flex;
  flex-direction: column;
  padding: 1rem;
  border-radius: 16px;
}
.logo {
  margin-bottom: 2rem;
  text-align: center;
  color: var(--primary-color);
}
nav {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}
.nav-item {
  display: flex;
  align-items: center;
  padding: 1rem;
  color: var(--text-color);
  text-decoration: none;
  border-radius: 8px;
  transition: background 0.3s;
}
.nav-item:hover, .nav-item.active {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}
.logout-btn {
  width: 100%;
  background: rgba(255, 50, 50, 0.2);
  color: #ff6b6b;
}
.logout-btn:hover {
  background: rgba(255, 50, 50, 0.4);
}
</style>
