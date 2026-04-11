import { defineStore } from 'pinia'

const STORAGE_KEY = 'atm-theme'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    theme: (typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme')) || 'light',
  }),
  actions: {
    apply(next) {
      this.theme = next
      document.documentElement.setAttribute('data-theme', next)
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch (e) {
        // ignore
      }
    },
    toggle() {
      this.apply(this.theme === 'dark' ? 'light' : 'dark')
    },
  },
})
