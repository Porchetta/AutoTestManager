<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import SidebarNav from '../components/SidebarNav.vue'

const authStore = useAuthStore()
const route = useRoute()

const title = computed(() => {
  if (route.path.startsWith('/rtd')) return 'RTD Test'
  if (route.path.startsWith('/ezdfs')) return 'ezDFS Test'
  if (route.path.startsWith('/admin')) return 'Admin'
  if (route.path.startsWith('/mypage')) return 'My Page'
  return 'Dashboard'
})
</script>

<template>
  <div class="layout">
    <SidebarNav />
    <main class="layout-main">
      <header class="topbar">
        <div>
          <p class="eyebrow">AutoTestManager</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="topbar-meta">
          <span class="pill">{{ authStore.user?.module_name }}</span>
          <span class="pill pill-ghost">{{ authStore.user?.user_name }}</span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

