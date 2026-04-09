import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, apiPut, downloadFile } from '../api'

export const useEzdfsStore = defineStore('ezdfs', () => {
  const selectedModule = ref('')
  const selectedRule = ref('')
  const currentTask = ref(null)
  const tasks = ref([])
  const modules = ref([])
  const rules = ref([])

  async function loadInitialData() {
    modules.value = (await apiGet('/api/ezdfs/modules')).items
    await restoreSession()
    await refreshTasks()
  }

  async function loadRules() {
    if (!selectedModule.value) return
    rules.value = (await apiGet('/api/ezdfs/rules', { params: { module_name: selectedModule.value } })).items
  }

  async function saveSession() {
    await apiPut('/api/ezdfs/session', {
      selected_module: selectedModule.value,
      selected_rule: selectedRule.value,
      active_task_id: currentTask.value?.task_id || null,
      latest_status: currentTask.value?.status || null,
    })
  }

  async function restoreSession() {
    const session = (await apiGet('/api/ezdfs/session')).session || {}
    selectedModule.value = session.selected_module || ''
    selectedRule.value = session.selected_rule || ''
    if (selectedModule.value) {
      await loadRules()
    }
  }

  async function run(action) {
    const data = await apiPost(`/api/ezdfs/actions/${action}`, {
      module_name: selectedModule.value,
      rule_name: selectedRule.value,
    })
    currentTask.value = data.task
    await refreshTasks()
    await saveSession()
  }

  async function refreshTasks() {
    tasks.value = (await apiGet('/api/ezdfs/status')).items
    currentTask.value = tasks.value[0] || null
  }

  async function generateSummary(taskId) {
    await apiPost(`/api/ezdfs/results/${taskId}/summary`, {})
    await refreshTasks()
  }

  async function downloadRaw(taskId) {
    await downloadFile(`/api/ezdfs/results/${taskId}/raw`, `ezdfs_${taskId}_raw.txt`)
  }

  async function downloadSummary(taskId) {
    await downloadFile(`/api/ezdfs/results/${taskId}/summary`, `ezdfs_${taskId}_summary.xlsx`)
  }

  return {
    selectedModule,
    selectedRule,
    currentTask,
    tasks,
    modules,
    rules,
    loadInitialData,
    loadRules,
    saveSession,
    restoreSession,
    run,
    refreshTasks,
    generateSummary,
    downloadRaw,
    downloadSummary,
  }
})

