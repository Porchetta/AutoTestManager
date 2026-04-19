import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiDelete, apiGet, apiPost, apiPut, downloadFile } from '../api'
import { waitForTaskTerminalStatus } from '../composables/useTaskPolling'

const EMPTY_MACRO_STATE = () => ({
  searched: false,
  per_rule: [],
  has_any: false,
  error: '',
})

function computeRuleDiff(entry) {
  const oldList = Array.isArray(entry?.old_macros) ? entry.old_macros : []
  const newList = Array.isArray(entry?.new_macros) ? entry.new_macros : []
  const oldSet = new Set(oldList)
  const newSet = new Set(newList)
  return {
    old_diff: oldList.filter((item) => !newSet.has(item)),
    new_diff: newList.filter((item) => !oldSet.has(item)),
  }
}

export const useRtdStore = defineStore('rtd', () => {
  const currentStep = ref(1)
  const selectedBusinessUnit = ref('')
  const selectedLineName = ref('')
  const selectedRuleTargets = ref([])
  const selectedMacros = ref(EMPTY_MACRO_STATE())
  const majorChangeItems = ref({})
  const targetLines = ref([])
  const monitorRuleSelection = ref({})
  const tasks = ref([])
  const monitorItems = ref([])
  const copyVisibilityMap = ref({})
  const compileVisibilityMap = ref({})
  const testVisibilityMap = ref({})
  const svnUpload = ref({})

  const businessUnits = ref([])
  const lines = ref([])
  const rules = ref([])
  const ruleVersions = ref([])
  const targetLineOptions = ref([])
  const selectedRules = computed(() =>
    [...new Set(selectedRuleTargets.value.map((item) => item.rule_name).filter(Boolean))]
  )

  const macroReview = computed(() => {
    const perRule = Array.isArray(selectedMacros.value?.per_rule)
      ? selectedMacros.value.per_rule
      : []
    const oldDiffSet = new Set()
    const newDiffSet = new Set()
    const oldDiffList = []
    const newDiffList = []
    for (const entry of perRule) {
      const { old_diff, new_diff } = computeRuleDiff(entry)
      for (const item of old_diff) {
        if (!oldDiffSet.has(item)) {
          oldDiffSet.add(item)
          oldDiffList.push(item)
        }
      }
      for (const item of new_diff) {
        if (!newDiffSet.has(item)) {
          newDiffSet.add(item)
          newDiffList.push(item)
        }
      }
    }
    return {
      searched: Boolean(selectedMacros.value?.searched),
      error: String(selectedMacros.value?.error || ''),
      per_rule: perRule,
      old_macros: oldDiffList,
      new_macros: newDiffList,
      has_diff: oldDiffList.length > 0 || newDiffList.length > 0,
    }
  })

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
    major_change_items: majorChangeItems.value,
    target_lines: targetLines.value,
    monitor_rule_selection: monitorRuleSelection.value,
    active_task_ids: tasks.value.map((task) => task.task_id),
    compile_visibility_map: compileVisibilityMap.value,
    test_visibility_map: testVisibilityMap.value,
    svn_upload: svnUpload.value,
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
      selectedMacros.value = EMPTY_MACRO_STATE()
      return false
    }

    try {
      const result = await apiPost('/api/rtd/macros/compare', {
        line_name: selectedLineName.value,
        selected_rule_targets: selectedRuleTargets.value,
      })

      selectedMacros.value = {
        searched: true,
        per_rule: Array.isArray(result.per_rule) ? result.per_rule : [],
        has_any: Boolean(result.has_any),
        error: result.error || '',
      }
      return true
    } catch (error) {
      const detail =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        error?.message ||
        'Macro 조회에 실패했습니다.'

      selectedMacros.value = {
        searched: true,
        per_rule: [],
        has_any: false,
        error: typeof detail === 'string' ? detail : 'Macro 조회에 실패했습니다.',
      }
      return false
    }
  }

  function resetMacroState() {
    selectedMacros.value = EMPTY_MACRO_STATE()
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
    const storedMacros = session.selected_macros
    if (storedMacros && typeof storedMacros === 'object' && !Array.isArray(storedMacros)) {
      selectedMacros.value = {
        searched: Boolean(storedMacros.searched),
        per_rule: Array.isArray(storedMacros.per_rule) ? storedMacros.per_rule : [],
        has_any: Boolean(storedMacros.has_any),
        error: String(storedMacros.error || ''),
      }
    } else {
      selectedMacros.value = EMPTY_MACRO_STATE()
    }
    majorChangeItems.value = session.major_change_items || {}
    targetLines.value = session.target_lines || []
    monitorRuleSelection.value = session.monitor_rule_selection || {}
    compileVisibilityMap.value = session.compile_visibility_map || {}
    testVisibilityMap.value = session.test_visibility_map || {}
    svnUpload.value = session.svn_upload || {}
    syncMonitorRuleSelection()

    if (selectedBusinessUnit.value) await loadLines()
    if (selectedLineName.value) await loadRules()
    await refreshTasks()
    await refreshMonitor()
  }

  function resetAfterBusinessUnit() {
    selectedLineName.value = ''
    selectedRuleTargets.value = []
    resetMacroState()
    majorChangeItems.value = {}
    targetLines.value = []
    monitorRuleSelection.value = {}
    copyVisibilityMap.value = {}
    compileVisibilityMap.value = {}
    testVisibilityMap.value = {}
    svnUpload.value = {}
    lines.value = []
    rules.value = []
    ruleVersions.value = []
    targetLineOptions.value = []
  }

  function resetAfterLine() {
    selectedRuleTargets.value = []
    resetMacroState()
    majorChangeItems.value = {}
    targetLines.value = []
    monitorRuleSelection.value = {}
    copyVisibilityMap.value = {}
    compileVisibilityMap.value = {}
    testVisibilityMap.value = {}
    svnUpload.value = {}
    rules.value = []
    ruleVersions.value = []
  }

  function syncMonitorRuleSelection() {
    const validRules = new Set(selectedRuleTargets.value.map((item) => item.rule_name).filter(Boolean))
    const nextSelection = {}

    for (const targetLine of targetLines.value) {
      const selectedRule = monitorRuleSelection.value[targetLine]
      nextSelection[targetLine] =
        selectedRule && selectedRule !== '__ALL__' && validRules.has(selectedRule)
          ? selectedRule
          : '__ALL__'
    }

    monitorRuleSelection.value = nextSelection
  }

  function buildExecutionPayload(selectedRule = '__ALL__') {
    const normalizedRule = String(selectedRule || '').trim()
    if (!normalizedRule || normalizedRule === '__ALL__') {
      return sessionPayload.value
    }

    const filteredRuleTargets = selectedRuleTargets.value.filter((item) => item.rule_name === normalizedRule)
    if (!filteredRuleTargets.length) {
      return {
        ...sessionPayload.value,
        selected_rules: [],
        selected_rule_targets: [],
        selected_macros: EMPTY_MACRO_STATE(),
      }
    }
    const filteredPerRule = (selectedMacros.value?.per_rule || []).filter(
      (entry) => entry?.rule_name === normalizedRule,
    )

    return {
      ...sessionPayload.value,
      selected_rules: filteredRuleTargets.map((item) => item.rule_name),
      selected_rule_targets: filteredRuleTargets,
      selected_macros: {
        searched: Boolean(selectedMacros.value?.searched),
        per_rule: filteredPerRule,
        has_any: filteredPerRule.some(
          (entry) => (entry?.old_macros?.length || 0) + (entry?.new_macros?.length || 0) > 0,
        ),
        error: String(selectedMacros.value?.error || ''),
      },
    }
  }

  async function executeAction(action, overrideTargetLines = null, selectedRule = '__ALL__') {
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
      payload: buildExecutionPayload(selectedRule),
    })
    tasks.value = data.items
    if (action === 'copy') {
      for (const line of lines) {
        copyVisibilityMap.value[line] = true
      }
    }
    if (action === 'compile') {
      for (const line of lines) {
        compileVisibilityMap.value[line] = true
      }
    }
    if (action === 'test' || action === 'retest') {
      for (const line of lines) {
        testVisibilityMap.value[line] = true
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

    const idleAction = { status: 'IDLE', status_text: '이력 없음', message: '-' }

    monitorItems.value = (
      await apiGet('/api/rtd/monitor', {
        params: {
          target_lines: targetLines.value.join(','),
        },
      })
    ).items.map((item) => {
      const result = { ...item }

      const copyStatus = item.copy?.status
      if (copyStatus === 'RUNNING' || copyStatus === 'PENDING') {
        copyVisibilityMap.value[item.target_name] = true
      } else if (!((copyStatus === 'DONE' || copyStatus === 'FAIL') && copyVisibilityMap.value[item.target_name])) {
        result.copy = { ...(item.copy || {}), ...idleAction }
      }

      const compileStatus = item.compile?.status
      if (compileStatus === 'RUNNING' || compileStatus === 'PENDING') {
        compileVisibilityMap.value[item.target_name] = true
      } else if (!((compileStatus === 'DONE' || compileStatus === 'FAIL') && compileVisibilityMap.value[item.target_name])) {
        result.compile = { ...(item.compile || {}), ...idleAction }
      }

      const testStatus = item.test?.status
      if (testStatus === 'RUNNING' || testStatus === 'PENDING') {
        testVisibilityMap.value[item.target_name] = true
      } else if (!((testStatus === 'DONE' || testStatus === 'FAIL') && testVisibilityMap.value[item.target_name])) {
        result.test = { ...(item.test || {}), ...idleAction }
      }

      return result
    })
  }

  async function generateSummary(taskId) {
    await apiPost(`/api/rtd/results/${taskId}/summary`, {})
    await refreshTasks()
  }

  async function downloadRaw(taskId, selectedRule = '__ALL__') {
    const isSingleRule = selectedRule && selectedRule !== '__ALL__'
    await downloadFile(`/api/rtd/results/${taskId}/raw`, isSingleRule ? `rtd_${taskId}_${selectedRule}.txt` : `rtd_${taskId}_raw.zip`, {
      params: {
        selected_rule: selectedRule,
      },
    })
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

  async function waitForTaskIds(taskIds, options = {}) {
    return waitForTaskTerminalStatus(
      async () => {
        await refreshTasks()
        await refreshMonitor()
      },
      (ids) => tasks.value.filter((task) => ids.includes(task.task_id)),
      taskIds,
      options,
    )
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
    resetMacroState()
    majorChangeItems.value = {}
    targetLines.value = []
    monitorRuleSelection.value = {}
    monitorItems.value = []
    copyVisibilityMap.value = {}
    compileVisibilityMap.value = {}
    testVisibilityMap.value = {}
    lines.value = []
    rules.value = []
    ruleVersions.value = []
    targetLineOptions.value = []
  }

  async function updateMajorChangeItem(ruleName, value) {
    if (!ruleName) return
    const nextItems = { ...majorChangeItems.value }
    if (value?.trim()) {
      nextItems[ruleName] = value
    } else {
      delete nextItems[ruleName]
    }
    majorChangeItems.value = nextItems
    await saveSession()
  }

  async function uploadSvn(adUser, adPassword) {
    const data = await apiPost('/api/rtd/svn-upload', {
      ad_user: adUser,
      ad_password: adPassword,
    })
    svnUpload.value = data.svn_upload || {}
    return svnUpload.value
  }

  return {
    currentStep,
    selectedBusinessUnit,
    selectedLineName,
    selectedRules,
    selectedMacros,
    majorChangeItems,
    macroReview,
    targetLines,
    monitorRuleSelection,
    selectedRuleTargets,
    tasks,
    monitorItems,
    businessUnits,
    lines,
    rules,
    ruleVersions,
    targetLineOptions,
    svnUpload,
    loadInitialData,
    loadLines,
    loadRules,
    loadRuleVersions,
    loadMacroReview,
    resetMacroState,
    saveSession,
    restoreSession,
    resetAfterBusinessUnit,
    resetAfterLine,
    syncMonitorRuleSelection,
    executeAction,
    refreshTasks,
    refreshMonitor,
    generateSummary,
    downloadRaw,
    downloadSummary,
    downloadAggregateSummary,
    waitForTaskIds,
    updateMajorChangeItem,
    uploadSvn,
    resetFlow,
  }
})
