import { createRouter, createWebHistory } from 'vue-router'

import { registerApiContext } from '../api'
import MainLayout from '../layouts/MainLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import RTDView from '../views/RTDView.vue'
import EzDFSView from '../views/EzDFSView.vue'
import AdminView from '../views/AdminView.vue'
import MyPageView from '../views/MyPageView.vue'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { guestOnly: true } },
    { path: '/signup', component: SignupView, meta: { guestOnly: true } },
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', component: DashboardView },
        { path: 'rtd', component: RTDView },
        { path: 'ezdfs', component: EzDFSView },
        { path: 'admin', component: AdminView, meta: { requiresAdmin: true } },
        { path: 'mypage', component: MyPageView },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  authStore.restore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return '/'
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return '/'
  }

  return true
})

registerApiContext({
  getAuthStore: () => useAuthStore(),
  getUiStore: () => useUiStore(),
  getRouter: () => router,
})

export default router

