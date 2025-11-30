<template>
  <div class="main-layout">
    <Sidebar />
    <main class="content glass-panel">
      <router-view></router-view>
    </main>
  </div>
</template>

<script setup>
import Sidebar from '../components/Sidebar.vue';
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: radial-gradient(circle at center, #2a2a2a, #000);
}
.content {
  flex: 1;
  margin: 2.5vh 2.5vh 2.5vh 0;
  padding: 2rem;
  overflow-y: auto;
  border-radius: 16px;
}
</style>
