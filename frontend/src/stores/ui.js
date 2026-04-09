import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', () => {
  const globalLoading = ref(false)
  const globalError = ref('')
  const globalNotice = ref('')
  const confirmDialogState = ref({
    open: false,
    title: '',
    message: '',
    confirmText: '확인',
    cancelText: '취소',
  })
  let confirmResolver = null

  function setLoading(value) {
    globalLoading.value = value
  }

  function setError(message) {
    globalError.value = message
  }

  function clearError() {
    globalError.value = ''
  }

  function setNotice(message) {
    globalNotice.value = message
    window.setTimeout(() => {
      if (globalNotice.value === message) {
        globalNotice.value = ''
      }
    }, 2800)
  }

  function clearNotice() {
    globalNotice.value = ''
  }

  function resolveConfirm(result) {
    if (confirmResolver) {
      confirmResolver(result)
      confirmResolver = null
    }

    confirmDialogState.value = {
      open: false,
      title: '',
      message: '',
      confirmText: '확인',
      cancelText: '취소',
    }
  }

  function confirmAction(message, options = {}) {
    confirmDialogState.value = {
      open: true,
      title: options.title || '확인 필요',
      message,
      confirmText: options.confirmText || '확인',
      cancelText: options.cancelText || '취소',
    }

    return new Promise((resolve) => {
      confirmResolver = resolve
    })
  }

  function confirmDialogOk() {
    resolveConfirm(true)
  }

  function confirmDialogCancel() {
    resolveConfirm(false)
  }

  return {
    globalLoading,
    globalError,
    globalNotice,
    confirmDialogState,
    setLoading,
    setError,
    clearError,
    setNotice,
    clearNotice,
    confirmAction,
    confirmDialogOk,
    confirmDialogCancel,
  }
})
