<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import SidebarNav from '../components/SidebarNav.vue'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const title = computed(() => {
  if (route.path.startsWith('/rtd')) return 'RTD Test'
  if (route.path.startsWith('/ezdfs')) return 'ezDFS Test'
  if (route.path.startsWith('/admin')) return 'Admin'
  if (route.path.startsWith('/mypage')) return 'My Page'
  return 'Dashboard'
})

async function logout() {
  await authStore.logout()
  router.push('/login')
}
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
          <span class="topbar-badge topbar-badge-accent">{{ authStore.user?.module_name }}</span>
          <span class="topbar-badge">{{ authStore.user?.user_name }}</span>
          <button class="topbar-logout-button" type="button" aria-label="Logout" @click="logout">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M7.5 4.5H5.5C4.94772 4.5 4.5 4.94772 4.5 5.5V14.5C4.5 15.0523 4.94772 15.5 5.5 15.5H7.5"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M11.5 6.5L15 10L11.5 13.5"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M8 10H15"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
