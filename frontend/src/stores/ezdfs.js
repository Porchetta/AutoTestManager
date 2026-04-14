import { ref } from "vue";
import { defineStore } from "pinia";

import { apiDelete, apiGet, apiPost, apiPut, downloadFile } from "../api";

export const useEzdfsStore = defineStore("ezdfs", () => {
  const currentStep = ref(1);
  const selectedModule = ref("");
  const selectedRule = ref("");
  const selectedRuleVersion = ref("");
  const selectedRuleOldVersion = ref("");
  const selectedRuleFileName = ref("");
  const selectedRules = ref([]);
  const subRulesSearched = ref(false);
  const subRules = ref([]);
  const subRuleMap = ref({});
  const selectedSubRules = ref([]);
  const majorChangeItems = ref({});
  const currentTask = ref(null);
  const tasks = ref([]);
  const modules = ref([]);
  const rules = ref([]);
  const subRuleError = ref("");
  const svnUpload = ref({});

  async function loadInitialData() {
    modules.value = (await apiGet("/api/ezdfs/modules")).items;
    await restoreSession();
    await refreshTasks();
  }

  async function loadRules() {
    if (!selectedModule.value) {
      rules.value = [];
      return;
    }

    rules.value = (
      await apiGet("/api/ezdfs/rules", {
        params: { module_name: selectedModule.value },
      })
    ).items;
  }

  async function loadSubRules() {
    if (!selectedModule.value || !selectedRule.value || !selectedRuleFileName.value) {
      subRulesSearched.value = false;
      subRules.value = [];
      selectedSubRules.value = [];
      subRuleError.value = "";
      return;
    }

    const data = await apiGet("/api/ezdfs/sub-rules", {
      params: {
        module_name: selectedModule.value,
        rule_name: selectedRule.value,
        file_name: selectedRuleFileName.value,
      },
    });
    subRulesSearched.value = true;
    subRules.value = data.items || [];
    subRuleError.value = data.error || "";
    selectedSubRules.value = subRuleError.value ? [] : [...subRules.value];
  }

  async function saveSession() {
    await apiPut("/api/ezdfs/session", {
      current_step: currentStep.value,
      selected_module: selectedModule.value,
      selected_rule: selectedRule.value,
      selected_rule_version: selectedRuleVersion.value,
      selected_rule_old_version: selectedRuleOldVersion.value,
      selected_rule_file_name: selectedRuleFileName.value,
      selected_rules: selectedRules.value,
      sub_rules_searched: subRulesSearched.value,
      sub_rules: subRules.value,
      sub_rule_map: subRuleMap.value,
      selected_sub_rules: selectedSubRules.value,
      major_change_items: majorChangeItems.value,
      active_task_id: currentTask.value?.task_id || null,
      latest_status: currentTask.value?.status || null,
      svn_upload: svnUpload.value,
    });
  }

  async function restoreSession() {
    const session = (await apiGet("/api/ezdfs/session")).session || {};
    currentStep.value = session.current_step || 1;
    selectedModule.value = session.selected_module || "";
    selectedRule.value = session.selected_rule || "";
    selectedRuleVersion.value = session.selected_rule_version || "";
    selectedRuleOldVersion.value = session.selected_rule_old_version || "";
    selectedRuleFileName.value = session.selected_rule_file_name || "";
    selectedRules.value =
      session.selected_rules ||
      (session.selected_rule && session.selected_rule_file_name
        ? [
            {
              rule_name: session.selected_rule,
              version: session.selected_rule_version || "",
              old_version: session.selected_rule_old_version || "",
              file_name: session.selected_rule_file_name,
            },
          ]
        : []);
    subRulesSearched.value = Boolean(session.sub_rules_searched);
    subRules.value = subRulesSearched.value ? (session.sub_rules || []) : [];
    subRuleMap.value = subRulesSearched.value ? (session.sub_rule_map || {}) : {};
    selectedSubRules.value = subRulesSearched.value ? (session.selected_sub_rules || []) : [];
    majorChangeItems.value = session.major_change_items || {};
    svnUpload.value = session.svn_upload || {};
    currentTask.value = session.active_task_id ? { task_id: session.active_task_id } : null;

    if (selectedModule.value) {
      await loadRules();
    }
    if (selectedRule.value && subRulesSearched.value && session.selected_sub_rules?.length) {
      selectedSubRules.value = session.selected_sub_rules.filter((item) =>
        subRules.value.includes(item),
      );
    }
  }

  async function selectModule(moduleName) {
    selectedModule.value = moduleName;
    selectedRule.value = "";
    selectedRuleVersion.value = "";
    selectedRuleOldVersion.value = "";
    selectedRuleFileName.value = "";
    selectedRules.value = [];
    subRulesSearched.value = false;
    subRules.value = [];
    subRuleMap.value = {};
    selectedSubRules.value = [];
    majorChangeItems.value = {};
    subRuleError.value = "";
    if (currentStep.value > 2) {
      currentStep.value = 2;
    }
    await loadRules();
    await saveSession();
  }

  async function selectRule(ruleFileName) {
    const selectedItem = rules.value.find((item) => item.file_name === ruleFileName);
    selectedRule.value = selectedItem?.rule_name || "";
    selectedRuleVersion.value = selectedItem?.version || "";
    selectedRuleOldVersion.value = selectedItem?.old_version || "";
    selectedRuleFileName.value = selectedItem?.file_name || "";
    subRulesSearched.value = false;
    subRules.value = [];
    subRuleMap.value = {};
    selectedSubRules.value = [];
    majorChangeItems.value = {};
    subRuleError.value = "";
    if (currentStep.value > 3) {
      currentStep.value = 3;
    }
    await saveSession();
  }

  async function addSelectedRule() {
    if (!selectedRule.value || !selectedRuleFileName.value) {
      return false;
    }

    const alreadyExists = selectedRules.value.some(
      (item) =>
        item.file_name === selectedRuleFileName.value ||
        (
        item.rule_name === selectedRule.value &&
          item.version === selectedRuleVersion.value
        ),
    );

    if (alreadyExists) {
      return false;
    }

    selectedRules.value = [
      ...selectedRules.value,
      {
        rule_name: selectedRule.value,
        version: selectedRuleVersion.value,
        old_version: selectedRuleOldVersion.value,
        file_name: selectedRuleFileName.value,
      },
    ];
    subRulesSearched.value = false;
    subRules.value = [];
    subRuleMap.value = {};
    selectedSubRules.value = [];
    majorChangeItems.value = {};
    subRuleError.value = "";
    await saveSession();
    return true;
  }

  async function removeSelectedRule(index) {
    selectedRules.value = selectedRules.value.filter((_, itemIndex) => itemIndex !== index);
    subRulesSearched.value = false;
    subRules.value = [];
    subRuleMap.value = {};
    selectedSubRules.value = [];
    subRuleError.value = "";
    await saveSession();
  }

  async function searchSubRules() {
    if (!selectedModule.value || !selectedRules.value.length) {
      subRulesSearched.value = false;
      subRules.value = [];
      selectedSubRules.value = [];
      subRuleError.value = "";
      await saveSession();
      return;
    }

    const aggregatedItems = [];
    const seen = new Set();
    const nextSubRuleMap = {};
    for (const selectedItem of selectedRules.value) {
      const data = await apiGet("/api/ezdfs/sub-rules", {
        params: {
          module_name: selectedModule.value,
          rule_name: selectedItem.rule_name,
          file_name: selectedItem.file_name,
        },
      });

      if (data.error) {
        subRulesSearched.value = true;
        subRules.value = [];
        subRuleMap.value = {};
        selectedSubRules.value = [];
        subRuleError.value = data.error;
        await saveSession();
        return;
      }

      const ruleItems = [];
      for (const item of data.items || []) {
        ruleItems.push(item);
        if (!seen.has(item)) {
          seen.add(item);
          aggregatedItems.push(item);
        }
      }
      nextSubRuleMap[selectedItem.rule_name] = ruleItems;
    }

    subRulesSearched.value = true;
    subRules.value = aggregatedItems;
    subRuleMap.value = nextSubRuleMap;
    selectedSubRules.value = [...aggregatedItems];
    subRuleError.value = "";
    await saveSession();
  }

  async function toggleSubRuleSelection(item, checked) {
    if (checked) {
      if (!selectedSubRules.value.includes(item)) {
        selectedSubRules.value = [...selectedSubRules.value, item];
      }
    } else {
      selectedSubRules.value = selectedSubRules.value.filter((value) => value !== item);
    }
    await saveSession();
  }

  async function selectAllSubRules() {
    selectedSubRules.value = [...subRules.value];
    await saveSession();
  }

  async function clearAllSubRules() {
    selectedSubRules.value = [];
    await saveSession();
  }

  async function setCurrentStep(step) {
    currentStep.value = step;
    await saveSession();
  }

  async function run(action = "test") {
    const data = await apiPost(`/api/ezdfs/actions/${action}`, {
      module_name: selectedModule.value,
      rule_name: selectedRule.value,
      payload: {
        current_step: currentStep.value,
        selected_module: selectedModule.value,
        selected_rule: selectedRule.value,
        selected_rule_version: selectedRuleVersion.value,
        selected_rule_file_name: selectedRuleFileName.value,
        selected_rules: selectedRules.value,
        sub_rules: subRules.value,
        sub_rule_map: subRuleMap.value,
        selected_sub_rules: selectedSubRules.value,
        major_change_items: majorChangeItems.value,
      },
    });
    currentTask.value = data.task;
    await refreshTasks();
    await saveSession();
    return data.task;
  }

  async function runRule(action = "test", ruleItem = null) {
    const payloadRule = ruleItem || {
      rule_name: selectedRule.value,
      version: selectedRuleVersion.value,
      old_version: selectedRuleOldVersion.value,
      file_name: selectedRuleFileName.value,
    };

    if (!payloadRule?.rule_name) {
      throw new Error("rule_name is required");
    }

    const data = await apiPost(`/api/ezdfs/actions/${action}`, {
      module_name: selectedModule.value,
      rule_name: payloadRule.rule_name,
      payload: {
        current_step: currentStep.value,
        selected_module: selectedModule.value,
        selected_rule: payloadRule.rule_name,
        selected_rule_version: payloadRule.version || "",
        selected_rule_old_version: payloadRule.old_version || "",
        selected_rule_file_name: payloadRule.file_name || "",
        selected_rules: selectedRules.value,
        sub_rules: subRules.value,
        sub_rule_map: subRuleMap.value,
        selected_sub_rules: selectedSubRules.value,
        major_change_items: majorChangeItems.value,
      },
    });
    currentTask.value = data.task;
    await refreshTasks();
    await saveSession();
    return data.task;
  }

  async function runAllRules(action = "test") {
    const createdTasks = [];
    for (const item of selectedRules.value) {
      const task = await runRule(action, item);
      createdTasks.push(task);
    }
    return createdTasks;
  }

  async function waitForTasks(taskIds, intervalMs = 1200, timeoutMs = 10 * 60 * 1000) {
    const startedAt = Date.now();
    const targetIds = new Set(taskIds.filter(Boolean));
    if (!targetIds.size) {
      return [];
    }

    while (Date.now() - startedAt < timeoutMs) {
      await refreshTasks();
      const resolved = tasks.value.filter((task) => targetIds.has(task.task_id));
      if (
        resolved.length === targetIds.size &&
        resolved.every((task) => ["DONE", "FAIL", "CANCELED"].includes(task.status))
      ) {
        return resolved;
      }
      await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
    }

    throw new Error("작업 완료를 기다리는 중 시간이 초과되었습니다.");
  }

  async function generateReportsForTasks(taskIds) {
    const doneTaskIds = taskIds.filter((taskId) =>
      tasks.value.some((task) => task.task_id === taskId && task.status === "DONE"),
    );
    if (!doneTaskIds.length) {
      throw new Error("완료된 테스트 결과가 없습니다.");
    }
    await downloadFile("/api/ezdfs/results/aggregate-summary", "ezdfs_test_report.xlsx", {
      method: "post",
      data: {
        module_name: selectedModule.value,
        task_ids: doneTaskIds,
      },
    });
    await refreshTasks();
  }

  async function refreshTasks() {
    tasks.value = (await apiGet("/api/ezdfs/status")).items;
    if (currentTask.value?.task_id) {
      currentTask.value =
        tasks.value.find((item) => item.task_id === currentTask.value.task_id) ||
        tasks.value[0] ||
        null;
    } else {
      currentTask.value = tasks.value[0] || null;
    }
  }

  async function generateSummary(taskId) {
    await apiPost(`/api/ezdfs/results/${taskId}/summary`, {});
    await refreshTasks();
  }

  async function generateAndDownloadSummary(taskId) {
    await generateSummary(taskId);
    await downloadSummary(taskId);
  }

  async function downloadRaw(taskId) {
    await downloadFile(`/api/ezdfs/results/${taskId}/raw`, `ezdfs_${taskId}_raw.txt`);
  }

  async function downloadSummary(taskId) {
    await downloadFile(`/api/ezdfs/results/${taskId}/summary`, `ezdfs_${taskId}_summary.xlsx`);
  }

  async function resetFlow() {
    currentStep.value = 1;
    selectedModule.value = "";
    selectedRule.value = "";
    selectedRuleVersion.value = "";
    selectedRuleOldVersion.value = "";
    selectedRuleFileName.value = "";
    selectedRules.value = [];
    subRulesSearched.value = false;
    subRules.value = [];
    subRuleMap.value = {};
    selectedSubRules.value = [];
    majorChangeItems.value = {};
    subRuleError.value = "";
    currentTask.value = null;
    svnUpload.value = {};
    rules.value = [];
    tasks.value = [];
    await apiDelete("/api/ezdfs/session");
  }

  async function updateMajorChangeItem(ruleName, value) {
    const nextItems = { ...majorChangeItems.value };
    if (!ruleName) {
      return;
    }

    if (value?.trim()) {
      nextItems[ruleName] = value;
    } else {
      delete nextItems[ruleName];
    }

    majorChangeItems.value = nextItems;
    await saveSession();
  }

  async function uploadSvn(adUser, adPassword) {
    const data = await apiPost("/api/ezdfs/svn-upload", {
      ad_user: adUser,
      ad_password: adPassword,
    });
    svnUpload.value = data.svn_upload || {};
    return svnUpload.value;
  }

  async function confirmSvnUpload() {
    svnUpload.value = {
      ...svnUpload.value,
      confirmed: true,
    };
    await saveSession();
  }

  return {
    currentStep,
    selectedModule,
    selectedRule,
    selectedRuleVersion,
    selectedRuleOldVersion,
    selectedRuleFileName,
    selectedRules,
    subRulesSearched,
    subRules,
    subRuleMap,
    selectedSubRules,
    majorChangeItems,
    currentTask,
    tasks,
    modules,
    rules,
    subRuleError,
    svnUpload,
    loadInitialData,
    loadRules,
    loadSubRules,
    saveSession,
    restoreSession,
    selectModule,
    selectRule,
    addSelectedRule,
    removeSelectedRule,
    searchSubRules,
    toggleSubRuleSelection,
    selectAllSubRules,
    clearAllSubRules,
    updateMajorChangeItem,
    uploadSvn,
    confirmSvnUpload,
    setCurrentStep,
    run,
    runRule,
    runAllRules,
    waitForTasks,
    refreshTasks,
    generateSummary,
    generateAndDownloadSummary,
    generateReportsForTasks,
    downloadRaw,
    downloadSummary,
    resetFlow,
  };
});
