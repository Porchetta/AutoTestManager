import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiDelete, apiGet, apiPost, apiPut, downloadFile } from '../api'

export const useRtdStore = defineStore('rtd', () => {
  const currentStep = ref(1)
  const selectedBusinessUnit = ref('')
  const selectedLineName = ref('')
  const selectedRuleTargets = ref([])
  const selectedMacros = ref([])
  const macroReview = ref({
    searched: false,
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

  function normalizeTargetLineName(lineName) {
    return String(lineName || '').replace(/_TARGET\b/gi, '')
  }

  const sessionPayload = computed(() => ({
    current_step: currentStep.value,
    selected_business_unit: selectedBusinessUnit.value,
    selected_line_name: selectedLineName.value,
    selected_rules: selectedRules.value,
    selected_rule_targets: selectedRuleTargets.value,
    selected_macros: selectedMacros.value,
    selected_versions: {},
    macro_review: macroReview.value,
    target_lines: targetLines.value,
    active_task_ids: tasks.value.map((task) => task.task_id),
  }))

  async function loadInitialData() {
    const items = (await apiGet('/api/rtd/business-units')).items
    const priority = ['memory', 'foundry']
    const rank = (name) => {
      const idx = priority.indexOf(String(name).trim().toLowerCase())
      return idx === -1 ? priority.length : idx
    }
    businessUnits.value = [...items].sort((a, b) => rank(a) - rank(b))
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
      selectedMacros.value = []
      macroReview.value = {
        searched: false,
        old_macros: [],
        new_macros: [],
        has_diff: false,
        error: '',
      }
      return false
    }

    try {
      const result = await apiPost('/api/rtd/macros/compare', {
        line_name: selectedLineName.value,
        selected_rule_targets: selectedRuleTargets.value,
      })

      const allMacros = [...new Set([...(result.old_macros || []), ...(result.new_macros || [])])]
      selectedMacros.value = allMacros

      macroReview.value = {
        searched: true,
        old_macros: result.old_macros || [],
        new_macros: result.new_macros || [],
        has_diff: Boolean(result.has_diff),
        error: result.error || '',
      }
      return true
    } catch (error) {
      selectedMacros.value = []
      const detail =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        error?.message ||
        'Macro 조회에 실패했습니다.'

      macroReview.value = {
        searched: true,
        old_macros: [],
        new_macros: [],
        has_diff: false,
        error: typeof detail === 'string' ? detail : 'Macro 조회에 실패했습니다.',
      }
      return false
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
    selectedMacros.value = Array.isArray(session.selected_macros) ? session.selected_macros : []
    macroReview.value = {
      searched: Boolean(session.macro_review?.searched),
      old_macros: session.macro_review?.old_macros || [],
      new_macros: session.macro_review?.new_macros || [],
      has_diff: Boolean(session.macro_review?.has_diff),
      error: session.macro_review?.error || '',
    }
    targetLines.value = session.target_lines || []

    if (selectedBusinessUnit.value) await loadLines()
    if (selectedLineName.value) await loadRules()
    await refreshTasks()
    await refreshMonitor()
  }

  function resetAfterBusinessUnit() {
    selectedLineName.value = ''
    selectedRuleTargets.value = []
    selectedMacros.value = []
    macroReview.value = { searched: false, old_macros: [], new_macros: [], has_diff: false, error: '' }
    targetLines.value = []
    lines.value = []
    rules.value = []
    ruleVersions.value = []
    targetLineOptions.value = []
  }

  function resetAfterLine() {
    selectedRuleTargets.value = []
    selectedMacros.value = []
    macroReview.value = { searched: false, old_macros: [], new_macros: [], has_diff: false, error: '' }
    targetLines.value = []
    rules.value = []
    ruleVersions.value = []
  }

  async function executeAction(action, overrideTargetLines = null) {
    let lines = overrideTargetLines || targetLines.value
    if (action === 'copy') {
      lines = lines.filter((line) => normalizeTargetLineName(line) !== selectedLineName.value)
    }

    if (!lines.length) {
      tasks.value = []
      return []
    }

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
    return data.items
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

  async function resetFlow() {
    try {
      await apiDelete('/api/rtd/session')
    } catch {
      // Keep local reset even if server session deletion fails.
    }

    currentStep.value = 1
    selectedBusinessUnit.value = ''
    selectedLineName.value = ''
    selectedRuleTargets.value = []
    selectedMacros.value = []
    macroReview.value = {
      searched: false,
      old_macros: [],
      new_macros: [],
      has_diff: false,
      error: '',
    }
    targetLines.value = []
    monitorItems.value = []
    copyVisibilityMap.value = {}
    lines.value = []
    rules.value = []
    ruleVersions.value = []
    targetLineOptions.value = []
  }

  return {
    currentStep,
    selectedBusinessUnit,
    selectedLineName,
    selectedRules,
    selectedMacros,
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
    resetFlow,
  }
})
