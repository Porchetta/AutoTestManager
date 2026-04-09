<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const menus = computed(() => {
  const baseMenus = [
    { label: 'DashBoard', path: '/' },
    { label: 'RTD Test', path: '/rtd' },
    { label: 'ezDFS Test', path: '/ezdfs' },
    { label: 'My Page', path: '/mypage' },
  ]

  if (authStore.isAdmin) {
    baseMenus.splice(3, 0, { label: 'Admin', path: '/admin' })
  }

  return baseMenus
})

async function logout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand-card">
      <p class="eyebrow">Command Center</p>
      <h2>AutoTest Manager</h2>
      <p class="brand-copy">
        RTD와 ezDFS 테스트 흐름을 한 화면에서 조정하는 다크 모드 운영 콘솔입니다.
      </p>
    </div>

    <nav class="sidebar-nav">
      <RouterLink v-for="item in menus" :key="item.path" :to="item.path" class="nav-link">
        {{ item.label }}
      </RouterLink>
    </nav>

    <button class="button button-ghost logout-button" @click="logout">Logout</button>
  </aside>
</template>

