import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, apiPut } from '../api'
import { useUiStore } from './ui'

const STORAGE_KEY = 'atm-auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref('')
  const user = ref(null)

  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => Boolean(user.value?.is_admin))

  function restore() {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return

    try {
      const parsed = JSON.parse(raw)
      token.value = parsed.token || ''
      user.value = parsed.user || null
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  function persist() {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: token.value,
        user: user.value,
      }),
    )
  }

  async function login(payload) {
    const uiStore = useUiStore()
    uiStore.setLoading(true)
    try {
      const data = await apiPost('/api/auth/login', payload)
      token.value = data.access_token
      user.value = data.user
      persist()
      uiStore.setNotice(`${data.user.user_name}님, 환영합니다.`)
      return data
    } finally {
      uiStore.setLoading(false)
    }
  }

  async function signup(payload) {
    const uiStore = useUiStore()
    uiStore.setLoading(true)
    try {
      return await apiPost('/api/auth/signup', payload)
    } finally {
      uiStore.setLoading(false)
    }
  }

  async function fetchMe() {
    const data = await apiGet('/api/auth/me')
    user.value = data.user
    persist()
    return data.user
  }

  async function changePassword(payload) {
    return await apiPut('/api/auth/password', payload)
  }

  function logoutLocal() {
    token.value = ''
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  async function logout() {
    try {
      await apiPost('/api/auth/logout', {})
    } finally {
      logoutLocal()
    }
  }

  return {
    token,
    user,
    isAdmin,
    isAuthenticated,
    restore,
    login,
    signup,
    fetchMe,
    changePassword,
    logout,
    logoutLocal,
  }
})
