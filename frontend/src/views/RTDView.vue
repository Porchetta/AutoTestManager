<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../stores/rtd";
import { useUiStore } from "../stores/ui";

const rtdStore = useRtdStore();
const uiStore = useUiStore();

const {
  currentStep,
  selectedBusinessUnit,
  selectedLineName,
  selectedRuleTargets,
  selectedMacros,
  macroReview,
  targetLines,
  monitorItems,
  businessUnits,
  lines,
  rules,
  ruleVersions,
  targetLineOptions,
} = storeToRefs(rtdStore);

const steps = [
  "사업부 선택",
  "개발 라인 선택",
  "Rule 선택",
  "Macro 확인",
  "타겟 라인 선택",
  "Test 실행",
];

const ruleCandidate = ref("");
const ruleCandidateNewVersion = ref("");
const ruleCandidateOldVersion = ref("");
const macroSearchLoading = ref(false);
const resetFlowLoading = ref(false);
const executeAllLoading = ref(false);

function displayTargetLineName(targetLine) {
  return String(targetLine || "").replace(/_TARGET\b/gi, "");
}

function isDevLineTarget(targetLine) {
  return displayTargetLineName(targetLine) === selectedLineName.value;
}

function monitorStatusChip(item) {
  const ownerMatch = String(item.status_text || "").match(/\(([^)]+)\)\s*$/);
  const owner = ownerMatch?.[1] || "";

  if (item.compile?.status === "RUNNING") {
    return owner ? `Compiling [${owner}]` : "Compiling";
  }
  if (item.test?.status === "RUNNING") {
    return owner ? `Testing [${owner}]` : "Testing";
  }
  if (item.copy?.status === "RUNNING") {
    return owner ? `Copying [${owner}]` : "Copying";
  }
  if (
    item.compile?.status === "PENDING" ||
    item.test?.status === "PENDING" ||
    item.copy?.status === "PENDING"
  ) {
    return owner ? `대기 [${owner}]` : "대기";
  }
  return "대기";
}

function monitorActionDisplay(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return "✓";
  if (normalized === "FAIL") return "✕";
  return "";
}

function monitorActionIconClass(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return "is-success";
  if (normalized === "FAIL") return "is-fail";
  return "";
}

function monitorDownloadDisplay(enabled) {
  return enabled ? "⬇" : "—";
}

function monitorFailureReason(action) {
  if (!action || action.status !== "FAIL") return "";
  return action.message && action.message !== "-" ? action.message : "";
}

function monitorActionClass(status) {
  if (status === "DONE") return "is-success";
  if (status === "FAIL") return "is-fail";
  if (status === "PENDING") return "is-pending";
  if (status === "RUNNING") return "is-running";
  return "is-idle";
}

function showMonitorSpinner(status) {
  return status === "PENDING" || status === "RUNNING";
}

let pollId = null;

const canProceed = computed(() => {
  if (currentStep.value === 1) return Boolean(selectedBusinessUnit.value);
  if (currentStep.value === 2) return Boolean(selectedLineName.value);
  if (currentStep.value === 3) return selectedRuleTargets.value.length > 0;
  if (currentStep.value === 4) return true;
  if (currentStep.value === 5) return targetLines.value.length > 0;
  return true;
});

const selectionStats = computed(() => [
  { label: "사업부", value: selectedBusinessUnit.value || "미선택" },
  { label: "개발 라인", value: selectedLineName.value || "미선택" },
  {
    label: "Rule",
    value: selectedRuleTargets.value.length
      ? `${selectedRuleTargets.value.length}개`
      : "미선택",
  },
  {
    label: "Macro",
    value: !macroReview.value.searched
      ? "미탐색"
      : macroReview.value.error
        ? "오류"
        : `${selectedMacros.value.length}개`,
  },
  {
    label: "타겟 라인",
    value: targetLines.value.length
      ? `${targetLines.value.length}개 선택`
      : "미선택",
  },
]);

onMounted(async () => {
  await rtdStore.loadInitialData();
  pollId = window.setInterval(() => {
    rtdStore.refreshTasks();
    rtdStore.refreshMonitor();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollId) window.clearInterval(pollId);
});

async function selectBusinessUnit() {
  rtdStore.resetAfterBusinessUnit();
  ruleCandidate.value = "";
  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  await rtdStore.loadLines();
  await rtdStore.saveSession();
}

async function selectLine() {
  rtdStore.resetAfterLine();
  ruleCandidate.value = "";
  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  await rtdStore.loadRules();
  await rtdStore.saveSession();
}

async function selectRuleCandidate() {
  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  if (ruleCandidate.value === "error") {
    return;
  }
  await rtdStore.loadRuleVersions(ruleCandidate.value);
  const versions = rtdStore.ruleVersions;
  if (versions.length >= 1) {
    ruleCandidateNewVersion.value = versions[0];
  }
  if (versions.length >= 2) {
    ruleCandidateOldVersion.value = versions[1];
  }
}

async function addRuleTarget() {
  if (ruleCandidate.value === "error") {
    uiStore.setError(
      "Rule 목록을 가져오지 못했습니다. 개발 서버 연결과 경로를 확인해주세요.",
    );
    return;
  }

  if (
    !ruleCandidate.value ||
    !ruleCandidateNewVersion.value ||
    !ruleCandidateOldVersion.value
  ) {
    uiStore.setError("Rule, New version, Old version을 모두 선택해주세요.");
    return;
  }

  const exists = selectedRuleTargets.value.some(
    (item) =>
      item.rule_name === ruleCandidate.value &&
      item.new_version === ruleCandidateNewVersion.value &&
      item.old_version === ruleCandidateOldVersion.value,
  );

  if (exists) {
    uiStore.setError("이미 추가된 Rule 조합입니다.");
    return;
  }

  selectedRuleTargets.value.push({
    rule_name: ruleCandidate.value,
    new_version: ruleCandidateNewVersion.value,
    old_version: ruleCandidateOldVersion.value,
  });
  selectedMacros.value = [];
  macroReview.value = {
    searched: false,
    old_macros: [],
    new_macros: [],
    has_diff: false,
    error: "",
  };
  targetLines.value = [];
  await rtdStore.saveSession();

  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  uiStore.setNotice(
    `${ruleCandidate.value} Rule이 테스트 대상으로 추가되었습니다.`,
  );
}

async function removeRuleTarget(index) {
  selectedRuleTargets.value.splice(index, 1);
  selectedMacros.value = [];
  macroReview.value = {
    searched: false,
    old_macros: [],
    new_macros: [],
    has_diff: false,
    error: "",
  };
  targetLines.value = [];
  await rtdStore.saveSession();
}

async function searchMacros() {
  if (macroSearchLoading.value) {
    return;
  }
  if (!selectedLineName.value || !selectedRuleTargets.value.length) {
    uiStore.setError("먼저 테스트 대상 Rule을 추가해주세요.");
    return;
  }

  macroSearchLoading.value = true;
  try {
    const success = await rtdStore.loadMacroReview();
    await rtdStore.saveSession();

    if (!success || macroReview.value.error) {
      return;
    }

    if (macroReview.value.has_diff) {
      uiStore.setNotice("Macro 탐색이 완료되었습니다.");
      return;
    }

    uiStore.setNotice("Macro 탐색이 완료되었습니다. 차이가 없습니다.");
  } finally {
    macroSearchLoading.value = false;
  }
}

function isMacroSelected(macroName) {
  return selectedMacros.value.includes(macroName);
}

async function toggleMacroSelection(macroName, checked) {
  if (!macroName) return;

  if (checked) {
    if (!selectedMacros.value.includes(macroName)) {
      selectedMacros.value = [...selectedMacros.value, macroName];
    }
  } else {
    selectedMacros.value = selectedMacros.value.filter(
      (item) => item !== macroName,
    );
  }

  await rtdStore.saveSession();
}

async function selectAllMacros(macroType) {
  const sourceItems =
    macroType === "old"
      ? macroReview.value.old_macros
      : macroReview.value.new_macros;
  const merged = [...new Set([...selectedMacros.value, ...sourceItems])];
  selectedMacros.value = merged;
  await rtdStore.saveSession();
}

async function clearAllMacros(macroType) {
  const sourceItems =
    macroType === "old"
      ? macroReview.value.old_macros
      : macroReview.value.new_macros;
  const sourceSet = new Set(sourceItems);
  selectedMacros.value = selectedMacros.value.filter(
    (item) => !sourceSet.has(item),
  );
  await rtdStore.saveSession();
}

async function nextStep() {
  if (!canProceed.value) {
    uiStore.setError("현재 단계의 필수 선택값을 먼저 입력해주세요.");
    return;
  }
  if (currentStep.value < 6) currentStep.value += 1;
  await rtdStore.saveSession();
  if (currentStep.value === 6) {
    await rtdStore.refreshMonitor();
  }
}

async function previousStep() {
  if (currentStep.value > 1) currentStep.value -= 1;
  await rtdStore.saveSession();
  if (currentStep.value === 6) {
    await rtdStore.refreshMonitor();
  }
}

async function goToStep(step) {
  if (step < 1 || step > 6) return;
  currentStep.value = step;
  await rtdStore.saveSession();
  if (currentStep.value === 6) {
    await rtdStore.refreshMonitor();
  }
}

async function run(action) {
  if (!targetLines.value.length) {
    uiStore.setError("타겟 라인을 먼저 선택해주세요.");
    return;
  }
  const items = await rtdStore.executeAction(action);
  if (action === "copy" && !items.length) {
    uiStore.setNotice("개발 라인은 복사 대상에서 제외되었습니다.");
    return;
  }
  await rtdStore.refreshMonitor();
  uiStore.setNotice(`${action.toUpperCase()} 요청이 등록되었습니다.`);
}

async function generateAggregateSummary() {
  if (!targetLines.value.length) {
    uiStore.setError("타겟 라인을 먼저 선택해주세요.");
    return;
  }
  await rtdStore.downloadAggregateSummary();
  uiStore.setNotice("테스트 결과서 생성이 완료되었습니다.");
}

async function executeAllProcess() {
  if (executeAllLoading.value) {
    return;
  }

  if (!targetLines.value.length) {
    uiStore.setError("타겟 라인을 먼저 선택해주세요.");
    return;
  }

  executeAllLoading.value = true;
  try {
    const copyItems = await rtdStore.executeAction("copy");
    if (copyItems.length) {
      const copyResults = await rtdStore.waitForTaskIds(
        copyItems.map((item) => item.task_id),
      );
      if (copyResults.some((item) => item.status !== "DONE")) {
        uiStore.setError("복사 단계에서 실패가 발생해 전체 실행을 중단했습니다.");
        return;
      }
    }

    const compileItems = await rtdStore.executeAction("compile");
    if (!compileItems.length) {
      uiStore.setError("컴파일 요청을 생성하지 못했습니다.");
      return;
    }
    const compileResults = await rtdStore.waitForTaskIds(
      compileItems.map((item) => item.task_id),
    );
    if (compileResults.some((item) => item.status !== "DONE")) {
      uiStore.setError("컴파일 단계에서 실패가 발생해 전체 실행을 중단했습니다.");
      return;
    }

    const testItems = await rtdStore.executeAction("test");
    if (!testItems.length) {
      uiStore.setError("테스트 요청을 생성하지 못했습니다.");
      return;
    }
    const testResults = await rtdStore.waitForTaskIds(
      testItems.map((item) => item.task_id),
    );
    if (testResults.some((item) => item.status !== "DONE")) {
      uiStore.setError("테스트 단계에서 실패가 발생해 전체 실행을 중단했습니다.");
      return;
    }

    await rtdStore.downloadAggregateSummary();
    uiStore.setNotice("전체 프로세스가 완료되었습니다.");
  } catch (error) {
    uiStore.setError(error?.message || "전체 실행 중 오류가 발생했습니다.");
  } finally {
    await rtdStore.refreshMonitor();
    executeAllLoading.value = false;
  }
}

async function selectAllTargets() {
  targetLines.value = [...targetLineOptions.value];
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function clearAllTargets() {
  targetLines.value = [];
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function updateTargetSelection() {
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function runSingleAction(action, targetName) {
  if (action === "copy" && isDevLineTarget(targetName)) {
    uiStore.setNotice("개발 라인은 복사 대상에서 제외됩니다.");
    return;
  }
  const items = await rtdStore.executeAction(action, [targetName]);
  if (action === "copy" && !items.length) {
    uiStore.setNotice("개발 라인은 복사 대상에서 제외되었습니다.");
    return;
  }
  await rtdStore.refreshMonitor();
  uiStore.setNotice(
    `${displayTargetLineName(targetName)} ${action.toUpperCase()} 요청이 등록되었습니다.`,
  );
}

async function resetFlow() {
  if (resetFlowLoading.value) {
    return;
  }

  resetFlowLoading.value = true;
  try {
    await rtdStore.resetFlow();
    ruleCandidate.value = "";
    ruleCandidateNewVersion.value = "";
    ruleCandidateOldVersion.value = "";
    uiStore.setNotice("RTD 진행 상태가 초기화되었습니다.");
  } finally {
    resetFlowLoading.value = false;
  }
}
</script>

<template>
  <section class="page-grid">
    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>RTD Test Manager</h3>
        <span class="muted">Step {{ currentStep }} / 6</span>
      </div>

      <div class="manager-banner">
        <div class="manager-banner-copy">
          <p class="eyebrow">RTD 개발자 Test Flow</p>
        </div>
        <div class="manager-inline-stats">
          <div
            v-for="item in selectionStats"
            :key="item.label"
            class="mini-stat"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </div>

      <div class="manager-step-strip">
        <button
          v-for="(label, index) in steps"
          :key="label"
          class="manager-step-button"
          :data-active="currentStep === index + 1"
          @click="goToStep(index + 1)"
        >
          <span class="step-chip-number">{{ index + 1 }}</span>
          <strong class="step-chip-label">{{ label }}</strong>
        </button>
      </div>

      <div class="rtd-manager-layout">
        <section class="manager-workspace">
          <div v-if="currentStep === 1" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 1</p>
                <h4>사업부 선택</h4>
              </div>
            </div>
            <div class="choice-grid choice-grid-inline">
              <button
                v-for="item in businessUnits"
                :key="item"
                class="choice-card"
                :data-selected="selectedBusinessUnit === item"
                @click="
                  selectedBusinessUnit = item;
                  selectBusinessUnit();
                "
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div v-else-if="currentStep === 2" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 2</p>
                <h4>개발 라인 선택</h4>
              </div>
            </div>
            <div class="choice-grid choice-grid-inline">
              <button
                v-for="item in lines"
                :key="item"
                class="choice-card"
                :data-selected="selectedLineName === item"
                @click="
                  selectedLineName = item;
                  selectLine();
                "
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div v-else-if="currentStep === 3" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 3</p>
                <h4>Rule 선택</h4>
              </div>
            </div>
            <div class="rule-builder-card rule-toolbar-card">
              <div class="rule-builder-row rule-toolbar-row">
                <label class="field rule-builder-field">
                  <span>1. Rule 선택</span>
                  <select
                    v-model="ruleCandidate"
                    @change="selectRuleCandidate()"
                  >
                    <option disabled value="">선택</option>
                    <option v-for="item in rules" :key="item" :value="item">
                      {{ item }}
                    </option>
                  </select>
                </label>
                <label class="field rule-builder-field">
                  <span>2. Old version 선택</span>
                  <select v-model="ruleCandidateOldVersion">
                    <option disabled value="">선택</option>
                    <option
                      v-for="item in ruleVersions"
                      :key="`rule-old-${item}`"
                      :value="item"
                    >
                      {{ item }}
                    </option>
                  </select>
                </label>
                <label class="field rule-builder-field">
                  <span>3. New version 선택</span>
                  <select v-model="ruleCandidateNewVersion">
                    <option disabled value="">선택</option>
                    <option
                      v-for="item in ruleVersions"
                      :key="`rule-new-${item}`"
                      :value="item"
                    >
                      {{ item }}
                    </option>
                  </select>
                </label>
                <div class="field rule-builder-action">
                  <span>&nbsp;</span>
                  <button class="button button-primary" @click="addRuleTarget">
                    추가
                  </button>
                </div>
              </div>
            </div>

            <div class="manager-section-head manager-section-head-compact">
              <div>
                <p class="eyebrow">Selection Tray</p>
                <div class="manager-section-title-inline">
                  <h4>추가된 테스트 대상 Rule</h4>
                  <span class="pill pill-ghost"
                    >{{ selectedRuleTargets.length }} Items</span
                  >
                </div>
              </div>
            </div>

            <div
              class="stack-list selection-tray-list"
              v-if="selectedRuleTargets.length"
            >
              <div
                v-for="(item, index) in selectedRuleTargets"
                :key="`${item.rule_name}-${item.new_version}-${item.old_version}`"
                class="stack-item rule-target-item selection-tray-item"
              >
                <div class="rule-target-copy">
                  <strong>{{ item.rule_name }}</strong>
                  <p class="muted">
                    New: {{ item.new_version }} | Old: {{ item.old_version }}
                  </p>
                </div>
                <button
                  class="button button-ghost"
                  @click="removeRuleTarget(index)"
                >
                  제거
                </button>
              </div>
            </div>
            <p v-else class="muted">아직 추가된 테스트 대상 Rule이 없습니다.</p>
          </div>

          <div v-else-if="currentStep === 4" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 4</p>
                <h4>Macro 확인</h4>
              </div>
            </div>
            <div class="manager-inline-actions macro-toolbar">
              <button
                class="button button-primary manager-inline-action"
                :disabled="macroSearchLoading || !selectedRuleTargets.length"
                @click="searchMacros"
              >
                <span
                  v-if="macroSearchLoading"
                  class="monitor-action-spinner manager-inline-spinner"
                ></span>
                <span>{{ macroSearchLoading ? "탐색중" : "탐색" }}</span>
              </button>
            </div>
            <div v-if="macroReview.error" class="stack-item macro-state-panel">
              <strong>Macro 조회 실패</strong>
              <p class="muted">{{ macroReview.error }}</p>
            </div>
            <div
              v-else-if="macroReview.searched"
              class="macro-review-grid macro-console-grid"
            >
              <div class="panel-subcard macro-console-card">
                <div class="panel-head">
                  <div class="macro-card-head-copy">
                    <h4>Old Macro</h4>
                    <span class="pill pill-ghost"
                      >{{ macroReview.old_macros.length }} Items</span
                    >
                  </div>
                  <div class="macro-card-actions">
                    <button
                      class="button button-ghost macro-card-action"
                      :disabled="!macroReview.old_macros.length"
                      @click="selectAllMacros('old')"
                    >
                      전체선택
                    </button>
                    <button
                      class="button button-ghost macro-card-action"
                      :disabled="!macroReview.old_macros.length"
                      @click="clearAllMacros('old')"
                    >
                      전체 해제
                    </button>
                  </div>
                </div>
                <div
                  class="stack-list macro-stack-list"
                  v-if="macroReview.old_macros.length"
                >
                  <div
                    v-for="item in macroReview.old_macros"
                    :key="`old-${item}`"
                    class="stack-item macro-select-item"
                  >
                    <span class="macro-select-label">{{ item }}</span>
                    <label class="macro-check">
                      <input
                        :checked="isMacroSelected(item)"
                        type="checkbox"
                        @change="
                          toggleMacroSelection(item, $event.target.checked)
                        "
                      />
                    </label>
                  </div>
                </div>
                <p v-else class="muted">차이가 있는 Old Macro가 없습니다.</p>
              </div>

              <div class="panel-subcard macro-console-card">
                <div class="panel-head">
                  <div class="macro-card-head-copy">
                    <h4>New Macro</h4>
                    <span class="pill pill-ghost"
                      >{{ macroReview.new_macros.length }} Items</span
                    >
                  </div>
                  <div class="macro-card-actions">
                    <button
                      class="button button-ghost macro-card-action"
                      :disabled="!macroReview.new_macros.length"
                      @click="selectAllMacros('new')"
                    >
                      전체선택
                    </button>
                    <button
                      class="button button-ghost macro-card-action"
                      :disabled="!macroReview.new_macros.length"
                      @click="clearAllMacros('new')"
                    >
                      전체 해제
                    </button>
                  </div>
                </div>
                <div
                  class="stack-list macro-stack-list"
                  v-if="macroReview.new_macros.length"
                >
                  <div
                    v-for="item in macroReview.new_macros"
                    :key="`new-${item}`"
                    class="stack-item macro-select-item"
                  >
                    <span class="macro-select-label">{{ item }}</span>
                    <label class="macro-check">
                      <input
                        :checked="isMacroSelected(item)"
                        type="checkbox"
                        @change="
                          toggleMacroSelection(item, $event.target.checked)
                        "
                      />
                    </label>
                  </div>
                </div>
                <p v-else class="muted">차이가 있는 New Macro가 없습니다.</p>
              </div>
            </div>
            <p v-if="macroReview.searched && !macroReview.error" class="muted">
              선택된 Macro만 복사 대상에 포함됩니다.
            </p>
          </div>

          <div v-else-if="currentStep === 5" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 5</p>
                <h4>타겟 라인 선택</h4>
              </div>
            </div>
            <div class="check-grid choice-grid-inline">
              <label
                v-for="item in targetLineOptions"
                :key="item"
                class="check-card"
              >
                <input
                  v-model="targetLines"
                  type="checkbox"
                  :value="item"
                  @change="updateTargetSelection()"
                />
                <span>{{ displayTargetLineName(item) }}</span>
              </label>
            </div>
            <div class="macro-card-actions">
              <button
                class="button button-ghost macro-card-action"
                @click="selectAllTargets"
              >
                전체 선택
              </button>
              <button
                class="button button-ghost macro-card-action"
                @click="clearAllTargets"
              >
                전체 해제
              </button>
            </div>
          </div>

          <div v-else class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 6</p>
                <h4>Test 실행</h4>
              </div>
            </div>

            <div class="operation-console">
              <div class="operation-console-main operation-console-main-full">
                <div class="operation-process-head">
                  <p class="eyebrow">Process all</p>
                </div>
                <div class="operation-process-rail">
                  <div class="operation-process-sequence">
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-1"
                        @click="run('copy')"
                      >
                        <strong>복사</strong>
                      </button>
                    </div>
                    <span class="operation-process-arrow" aria-hidden="true"
                      >→</span
                    >
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-2"
                        @click="run('compile')"
                      >
                        <strong>컴파일</strong>
                      </button>
                    </div>
                    <span class="operation-process-arrow" aria-hidden="true"
                      >→</span
                    >
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-3"
                        @click="run('test')"
                      >
                        <strong>테스트</strong>
                      </button>
                    </div>
                    <span class="operation-process-arrow" aria-hidden="true"
                      >→</span
                    >
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-4"
                        @click="generateAggregateSummary"
                      >
                        <strong>결과서 생성</strong>
                      </button>
                    </div>
                  </div>
                  <div class="operation-process-divider" aria-hidden="true"></div>
                  <div class="operation-process-execute">
                    <button
                      class="button button-primary operation-button operation-button-execute-all"
                      :disabled="executeAllLoading"
                      @click="executeAllProcess"
                    >
                      <strong>{{ executeAllLoading ? "Executing..." : "Execute all" }}</strong>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="wizard-actions">
            <span
              v-if="currentStep === 1"
              class="wizard-actions-spacer"
              aria-hidden="true"
            />
            <button
              v-if="currentStep > 1"
              class="button button-ghost"
              @click="previousStep"
            >
              이전
            </button>
            <button
              v-if="currentStep < 6"
              class="button button-primary"
              @click="nextStep"
            >
              다음
            </button>
          </div>
        </section>
      </div>
    </article>

    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>Target Status Monitor</h3>
        <button
          class="button button-ghost manager-inline-action"
          type="button"
          :disabled="resetFlowLoading"
          @click="resetFlow"
        >
          <span
            v-if="resetFlowLoading"
            class="monitor-action-spinner manager-inline-spinner"
          ></span>
          <span>{{ resetFlowLoading ? "초기화중" : "초기화" }}</span>
        </button>
      </div>
      <div class="task-grid monitor-board">
        <div
          v-for="item in monitorItems"
          :key="item.target_name"
          class="task-card monitor-card"
        >
          <div class="monitor-header">
            <strong class="monitor-line-name">{{
              displayTargetLineName(item.target_name)
            }}</strong>
            <span class="monitor-status-chip">{{
              monitorStatusChip(item)
            }}</span>
          </div>

          <div class="monitor-action-grid">
            <button
              class="monitor-action-button"
              :class="monitorActionClass(item.copy.status)"
              :title="
                isDevLineTarget(item.target_name)
                  ? '개발 라인은 복사 대상이 아닙니다.'
                  : monitorFailureReason(item.copy)
              "
              type="button"
              :disabled="isDevLineTarget(item.target_name)"
              @click="runSingleAction('copy', item.target_name)"
            >
              <strong>복사</strong>
              <span class="monitor-action-meta">
                <span
                  v-if="monitorActionDisplay(item.copy.status)"
                  :class="['monitor-action-emoji', monitorActionIconClass(item.copy.status)]"
                >
                  {{ monitorActionDisplay(item.copy.status) }}
                </span>
                <span
                  v-if="showMonitorSpinner(item.copy.status)"
                  class="monitor-action-spinner"
                ></span>
              </span>
            </button>

            <button
              class="monitor-action-button"
              :class="monitorActionClass(item.compile.status)"
              :title="monitorFailureReason(item.compile)"
              type="button"
              @click="runSingleAction('compile', item.target_name)"
            >
              <strong>컴파일</strong>
              <span class="monitor-action-meta">
                <span
                  v-if="monitorActionDisplay(item.compile.status)"
                  :class="['monitor-action-emoji', monitorActionIconClass(item.compile.status)]"
                >
                  {{ monitorActionDisplay(item.compile.status) }}
                </span>
                <span
                  v-if="showMonitorSpinner(item.compile.status)"
                  class="monitor-action-spinner"
                ></span>
              </span>
            </button>

            <button
              class="monitor-action-button"
              :class="monitorActionClass(item.test.status)"
              :title="monitorFailureReason(item.test)"
              type="button"
              @click="runSingleAction('test', item.target_name)"
            >
              <strong>테스트</strong>
              <span class="monitor-action-meta">
                <span
                  v-if="monitorActionDisplay(item.test.status)"
                  :class="['monitor-action-emoji', monitorActionIconClass(item.test.status)]"
                >
                  {{ monitorActionDisplay(item.test.status) }}
                </span>
                <span
                  v-if="showMonitorSpinner(item.test.status)"
                  class="monitor-action-spinner"
                ></span>
              </span>
            </button>

            <button
              class="monitor-action-button monitor-download-action"
              :class="{ 'is-disabled': !item.raw_download.enabled }"
              :disabled="!item.raw_download.enabled"
              type="button"
              @click="rtdStore.downloadRaw(item.raw_download.task_id)"
            >
              <strong>Raw Data</strong>
              <span class="monitor-action-meta">
                <span class="monitor-action-emoji">
                  {{ monitorDownloadDisplay(item.raw_download.enabled) }}
                </span>
              </span>
            </button>
          </div>
        </div>
        <p v-if="!monitorItems.length" class="muted">
          실행 제어에 들어오면 선택된 타겟 라인의 상태가 여기 표시됩니다.
        </p>
      </div>
    </article>
  </section>
</template>
