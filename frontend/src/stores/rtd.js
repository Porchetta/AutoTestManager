import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, apiPut, downloadFile } from '../api'

export const useRtdStore = defineStore('rtd', () => {
  const currentStep = ref(1)
  const selectedBusinessUnit = ref('')
  const selectedLineName = ref('')
  const selectedRuleTargets = ref([])
  const macroReview = ref({
    old_macros: [],
    new_macros: [],
    has_diff: false,
    error: '',
  })
  const targetLines = ref([])
  const tasks = ref([])
  const monitorItems = ref([])
  const copyVisibilityMap = ref({})

  const businessUnits = ref([])
  const lines = ref([])
  const rules = ref([])
  const ruleVersions = ref([])
  const targetLineOptions = ref([])
  const selectedRules = computed(() =>
    [...new Set(selectedRuleTargets.value.map((item) => item.rule_name).filter(Boolean))]
  )

  const sessionPayload = computed(() => ({
    current_step: currentStep.value,
    selected_business_unit: selectedBusinessUnit.value,
    selected_line_name: selectedLineName.value,
    selected_rules: selectedRules.value,
    selected_rule_targets: selectedRuleTargets.value,
    selected_macros: [],
    selected_versions: {},
    macro_review: macroReview.value,
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
    ruleVersions.value = []
  }

  async function loadRuleVersions(ruleName) {
    if (!ruleName) {
      ruleVersions.value = []
      return
    }
    if (ruleName === 'error') {
      ruleVersions.value = ['error']
      return
    }

    ruleVersions.value = (
      await apiGet('/api/rtd/versions/rules', {
        params: {
          rule_name: ruleName,
          line_name: selectedLineName.value,
        },
      })
    ).items
    ruleVersions.value = [...ruleVersions.value].sort((left, right) =>
      String(right ?? '').localeCompare(String(left ?? ''), undefined, {
        numeric: true,
        sensitivity: 'base',
      }),
    )
  }

  async function loadMacroReview() {
    if (!selectedLineName.value || !selectedRuleTargets.value.length) {
      macroReview.value = {
        old_macros: [],
        new_macros: [],
        has_diff: false,
        error: '',
      }
      return
    }

    const result = await apiPost('/api/rtd/macros/compare', {
      line_name: selectedLineName.value,
      selected_rule_targets: selectedRuleTargets.value,
    })

    macroReview.value = {
      old_macros: result.old_macros || [],
      new_macros: result.new_macros || [],
      has_diff: Boolean(result.has_diff),
      error: result.error || '',
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
    selectedRuleTargets.value =
      session.selected_rule_targets ||
      (session.selected_rules || []).map((ruleName) => ({
        rule_name: ruleName,
        new_version: '',
        old_version: '',
      }))
    macroReview.value = {
      old_macros: session.macro_review?.old_macros || [],
      new_macros: session.macro_review?.new_macros || [],
      has_diff: Boolean(session.macro_review?.has_diff),
      error: session.macro_review?.error || '',
    }
    targetLines.value = session.target_lines || []

    if (selectedBusinessUnit.value) await loadLines()
    if (selectedLineName.value) await loadRules()
    if (selectedRuleTargets.value.length) await loadMacroReview()
    await refreshTasks()
    await refreshMonitor()
  }

  function resetAfterBusinessUnit() {
    selectedLineName.value = ''
    selectedRuleTargets.value = []
    macroReview.value = { old_macros: [], new_macros: [], has_diff: false, error: '' }
    targetLines.value = []
    lines.value = []
    rules.value = []
    ruleVersions.value = []
    targetLineOptions.value = []
  }

  function resetAfterLine() {
    selectedRuleTargets.value = []
    macroReview.value = { old_macros: [], new_macros: [], has_diff: false, error: '' }
    targetLines.value = []
    rules.value = []
    ruleVersions.value = []
  }

  async function executeAction(action, overrideTargetLines = null) {
    const lines = overrideTargetLines || targetLines.value
    const data = await apiPost(`/api/rtd/actions/${action}`, {
      target_lines: lines,
      payload: sessionPayload.value,
    })
    tasks.value = data.items
    if (action === 'copy') {
      for (const line of lines) {
        copyVisibilityMap.value[line] = true
      }
    }
    await saveSession()
  }

  async function refreshTasks() {
    tasks.value = (await apiGet('/api/rtd/status')).items
  }

  async function refreshMonitor() {
    if (!targetLines.value.length) {
      monitorItems.value = []
      return
    }

    monitorItems.value = (
      await apiGet('/api/rtd/monitor', {
        params: {
          target_lines: targetLines.value.join(','),
        },
      })
    ).items.map((item) => {
      const copyStateVisible = copyVisibilityMap.value[item.target_name]
      const copyStatus = item.copy?.status

      if (copyStatus === 'RUNNING' || copyStatus === 'PENDING') {
        copyVisibilityMap.value[item.target_name] = true
        return item
      }

      if ((copyStatus === 'DONE' || copyStatus === 'FAIL') && copyStateVisible) {
        return item
      }

      return {
        ...item,
        copy: {
          ...(item.copy || {}),
          status: 'IDLE',
          status_text: '이력 없음',
          message: '-',
        },
      }
    })
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

  async function downloadAggregateSummary() {
    if (!targetLines.value.length) return
    await downloadFile('/api/rtd/results/aggregate-summary', 'rtd_test_report.xlsx', {
      params: {
        target_lines: targetLines.value.join(','),
      },
    })
  }

  return {
    currentStep,
    selectedBusinessUnit,
    selectedLineName,
    selectedRules,
    macroReview,
    targetLines,
    selectedRuleTargets,
    tasks,
    monitorItems,
    businessUnits,
    lines,
    rules,
    ruleVersions,
    targetLineOptions,
    loadInitialData,
    loadLines,
    loadRules,
    loadRuleVersions,
    loadMacroReview,
    saveSession,
    restoreSession,
    resetAfterBusinessUnit,
    resetAfterLine,
    executeAction,
    refreshTasks,
    refreshMonitor,
    generateSummary,
    downloadRaw,
    downloadSummary,
    downloadAggregateSummary,
  }
})
