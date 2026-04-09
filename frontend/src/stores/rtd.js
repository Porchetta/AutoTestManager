import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, apiPut, downloadFile } from '../api'

export const useRtdStore = defineStore('rtd', () => {
  const currentStep = ref(1)
  const selectedBusinessUnit = ref('')
  const selectedLineName = ref('')
  const selectedRules = ref([])
  const selectedMacros = ref([])
  const selectedVersions = ref({
    rule_old: '',
    rule_new: '',
    macro_old: '',
    macro_new: '',
  })
  const targetLines = ref([])
  const tasks = ref([])

  const businessUnits = ref([])
  const lines = ref([])
  const rules = ref([])
  const macros = ref([])
  const ruleVersions = ref([])
  const macroVersions = ref([])
  const targetLineOptions = ref([])

  const sessionPayload = computed(() => ({
    current_step: currentStep.value,
    selected_business_unit: selectedBusinessUnit.value,
    selected_line_name: selectedLineName.value,
    selected_rules: selectedRules.value,
    selected_macros: selectedMacros.value,
    selected_versions: selectedVersions.value,
    target_lines: targetLines.value,
    active_task_ids: tasks.value.map((task) => task.task_id),
  }))

  async function loadInitialData() {
    businessUnits.value = (await apiGet('/api/rtd/business-units')).items
    await restoreSession()
  }

  async function loadLines() {
    if (!selectedBusinessUnit.value) return
    lines.value = (await apiGet('/api/rtd/lines', { params: { business_unit: selectedBusinessUnit.value } })).items
    targetLineOptions.value = (
      await apiGet('/api/rtd/target-lines', { params: { business_unit: selectedBusinessUnit.value } })
    ).items
  }

  async function loadRules() {
    if (!selectedLineName.value) return
    rules.value = (await apiGet('/api/rtd/rules', { params: { line_name: selectedLineName.value } })).items
  }

  async function loadMacrosAndVersions() {
    if (!selectedRules.value.length) return
    const primaryRule = selectedRules.value[0]
    macros.value = (await apiGet('/api/rtd/macros', { params: { rule_name: primaryRule } })).items
    ruleVersions.value = (await apiGet('/api/rtd/versions/rules', { params: { rule_name: primaryRule } })).items

    const primaryMacro = selectedMacros.value[0] || macros.value[0]
    if (primaryMacro) {
      macroVersions.value = (
        await apiGet('/api/rtd/versions/macros', { params: { macro_name: primaryMacro } })
      ).items
    }
  }

  async function saveSession() {
    await apiPut('/api/rtd/session', sessionPayload.value)
  }

  async function restoreSession() {
    const session = (await apiGet('/api/rtd/session')).session || {}
    currentStep.value = session.current_step || 1
    selectedBusinessUnit.value = session.selected_business_unit || ''
    selectedLineName.value = session.selected_line_name || ''
    selectedRules.value = session.selected_rules || []
    selectedMacros.value = session.selected_macros || []
    selectedVersions.value = {
      rule_old: session.selected_versions?.rule_old || '',
      rule_new: session.selected_versions?.rule_new || '',
      macro_old: session.selected_versions?.macro_old || '',
      macro_new: session.selected_versions?.macro_new || '',
    }
    targetLines.value = session.target_lines || []

    if (selectedBusinessUnit.value) await loadLines()
    if (selectedLineName.value) await loadRules()
    if (selectedRules.value.length) await loadMacrosAndVersions()
    await refreshTasks()
  }

  function resetAfterBusinessUnit() {
    selectedLineName.value = ''
    selectedRules.value = []
    selectedMacros.value = []
    selectedVersions.value = { rule_old: '', rule_new: '', macro_old: '', macro_new: '' }
    targetLines.value = []
    lines.value = []
    rules.value = []
    macros.value = []
    ruleVersions.value = []
    macroVersions.value = []
    targetLineOptions.value = []
  }

  function resetAfterLine() {
    selectedRules.value = []
    selectedMacros.value = []
    selectedVersions.value = { rule_old: '', rule_new: '', macro_old: '', macro_new: '' }
    targetLines.value = []
    rules.value = []
    macros.value = []
    ruleVersions.value = []
    macroVersions.value = []
  }

  async function executeAction(action, overrideTargetLines = null) {
    const lines = overrideTargetLines || targetLines.value
    const data = await apiPost(`/api/rtd/actions/${action}`, {
      target_lines: lines,
      payload: sessionPayload.value,
    })
    tasks.value = data.items
    await saveSession()
  }

  async function refreshTasks() {
    tasks.value = (await apiGet('/api/rtd/status')).items
  }

  async function generateSummary(taskId) {
    await apiPost(`/api/rtd/results/${taskId}/summary`, {})
    await refreshTasks()
  }

  async function downloadRaw(taskId) {
    await downloadFile(`/api/rtd/results/${taskId}/raw`, `rtd_${taskId}_raw.txt`)
  }

  async function downloadSummary(taskId) {
    await downloadFile(`/api/rtd/results/${taskId}/summary`, `rtd_${taskId}_summary.xlsx`)
  }

  return {
    currentStep,
    selectedBusinessUnit,
    selectedLineName,
    selectedRules,
    selectedMacros,
    selectedVersions,
    targetLines,
    tasks,
    businessUnits,
    lines,
    rules,
    macros,
    ruleVersions,
    macroVersions,
    targetLineOptions,
    loadInitialData,
    loadLines,
    loadRules,
    loadMacrosAndVersions,
    saveSession,
    restoreSession,
    resetAfterBusinessUnit,
    resetAfterLine,
    executeAction,
    refreshTasks,
    generateSummary,
    downloadRaw,
    downloadSummary,
  }
})
