<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import StatusBadge from "../components/StatusBadge.vue";
import { useAuthStore } from "../stores/auth";
import { useEzdfsStore } from "../stores/ezdfs";
import { useUiStore } from "../stores/ui";

const authStore = useAuthStore();
const ezdfsStore = useEzdfsStore();
const uiStore = useUiStore();

const {
  currentStep,
  selectedModule,
  selectedRule,
  selectedRuleVersion,
  selectedRuleOldVersion,
  selectedRuleFileName,
  selectedRules,
  subRulesSearched,
  subRules,
  selectedSubRules,
  majorChangeItems,
  currentTask,
  tasks,
  modules,
  rules,
  subRuleError,
  svnUpload,
} = storeToRefs(ezdfsStore);

const steps = ["타겟 서버 선택", "Rule 선택", "Sub Rule 확인", "Test 실행"];
const resetFlowLoading = ref(false);
const subRuleSearchLoading = ref(false);
const testAllLoading = ref(false);
const reportAllLoading = ref(false);
const executeAllLoading = ref(false);
const svnUploading = ref(false);
const svnForm = ref({
  adUser: "",
  adPassword: "",
  svnNo: "",
});

const svnResultText = ref("");
const svnResultVisible = ref(false);
let pollId = null;

const canProceed = computed(() => {
  if (currentStep.value === 1) return Boolean(selectedModule.value);
  if (currentStep.value === 2) return Boolean(selectedRules.value.length);
  if (currentStep.value === 3)
    return subRulesSearched.value && !subRuleError.value;
  return true;
});

const selectionStats = computed(() => [
  { label: "Module", value: selectedModule.value || "미선택" },
  {
    label: "Rule",
    value: selectedRules.value.length
      ? `${selectedRules.value.length}개`
      : "미선택",
  },
  { label: "Version", value: selectedRuleVersion.value || "미선택" },
  { label: "Old Version", value: selectedRuleOldVersion.value || "미선택" },
  {
    label: "Sub Rule",
    value: !subRulesSearched.value
      ? "미탐색"
      : selectedSubRules.value.length
        ? `${selectedSubRules.value.length}/${subRules.value.length || 0}개`
        : subRules.value.length
          ? `0/${subRules.value.length}개`
          : "미확인",
  },
]);

const latestTaskByRule = computed(() => {
  const map = new Map();
  for (const item of tasks.value) {
    if (item.module_name !== selectedModule.value) {
      continue;
    }
    const ruleKey = item.rule_name || item.target_name;
    if (!map.has(ruleKey)) {
      map.set(ruleKey, item);
    }
  }
  return map;
});

const ruleTaskCards = computed(() =>
  selectedRules.value.map((item) => ({
    ...item,
    task: latestTaskByRule.value.get(item.rule_name) || null,
  })),
);

async function submitSvnUpload() {
  if (!svnForm.value.adUser || !svnForm.value.adPassword) {
    uiStore.setError("AD 계정과 비밀번호를 모두 입력해주세요.");
    return;
  }

  svnUploading.value = true;
  try {
    const result = await ezdfsStore.uploadSvn(
      svnForm.value.adUser,
      svnForm.value.adPassword,
    );
    svnForm.value.svnNo = result?.svn_no || "";
    svnForm.value.adPassword = "";
    uiStore.setNotice("SVN Upload가 완료되었습니다.");
  } finally {
    svnUploading.value = false;
  }
}

function showSvnResult() {
  svnResultText.value = svnUpload.value?.checkin_output || "SVN Upload 결과가 없습니다.";
  svnResultVisible.value = true;
}

function closeSvnResult() {
  svnResultVisible.value = false;
}

onMounted(async () => {
  await ezdfsStore.loadInitialData();
  svnForm.value = {
    adUser: svnUpload.value?.ad_user || authStore.user?.user_id || "",
    adPassword: "",
    svnNo: svnUpload.value?.svn_no || "",
  };
  pollId = window.setInterval(() => {
    ezdfsStore.refreshTasks();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollId) window.clearInterval(pollId);
});

async function nextStep() {
  if (!canProceed.value) {
    uiStore.setError("현재 단계의 필수 선택값을 먼저 입력해주세요.");
    return;
  }

  if (currentStep.value < 4) {
    currentStep.value += 1;
  }
  await ezdfsStore.saveSession();
}

async function previousStep() {
  if (currentStep.value > 1) {
    currentStep.value -= 1;
  }
  await ezdfsStore.saveSession();
}

async function goToStep(step) {
  if (step < 1 || step > 4) return;
  currentStep.value = step;
  await ezdfsStore.saveSession();
}

async function chooseModule(moduleName) {
  await ezdfsStore.selectModule(moduleName);
}

async function chooseRule(ruleName) {
  await ezdfsStore.selectRule(ruleName);
}

async function addRule() {
  if (!selectedRule.value) {
    uiStore.setError("Rule을 먼저 선택해주세요.");
    return;
  }

  const added = await ezdfsStore.addSelectedRule();
  if (!added) {
    uiStore.setError("이미 추가된 Rule입니다.");
    return;
  }

  uiStore.setNotice("Rule이 추가되었습니다.");
}

async function removeRule(index) {
  await ezdfsStore.removeSelectedRule(index);
}

async function searchSubRules() {
  if (!selectedRules.value.length) {
    uiStore.setError("추가된 Rule이 없습니다.");
    return;
  }

  subRuleSearchLoading.value = true;
  try {
    await ezdfsStore.searchSubRules();
    if (subRuleError.value) {
      uiStore.setError("Sub Rule 조회에 실패했습니다.");
      return;
    }
    uiStore.setNotice("Sub Rule 탐색이 완료되었습니다.");
  } finally {
    subRuleSearchLoading.value = false;
  }
}

async function toggleSubRule(item, checked) {
  await ezdfsStore.toggleSubRuleSelection(item, checked);
}

async function selectAllSubRules() {
  await ezdfsStore.selectAllSubRules();
}

async function clearAllSubRules() {
  await ezdfsStore.clearAllSubRules();
}

async function runTest() {
  if (!selectedModule.value || !selectedRules.value.length) {
    uiStore.setError("추가된 Rule이 없습니다.");
    return;
  }
  testAllLoading.value = true;
  try {
    await ezdfsStore.runAllRules("test");
    uiStore.setNotice("선택된 Rule 전체 TEST 요청이 등록되었습니다.");
  } finally {
    testAllLoading.value = false;
  }
}

async function runRuleTest(item) {
  await ezdfsStore.runRule("test", item);
  uiStore.setNotice(`${item.rule_name} TEST 요청이 등록되었습니다.`);
}

async function downloadRaw(task) {
  if (!task?.raw_result_ready) {
    uiStore.setError("다운로드 가능한 Raw Data가 없습니다.");
    return;
  }
  await ezdfsStore.downloadRaw(task.task_id);
}

async function updateMajorChange(ruleName, value) {
  await ezdfsStore.updateMajorChangeItem(ruleName, value);
}

async function generateReport() {
  const doneTasks = ruleTaskCards.value
    .map((item) => item.task)
    .filter((task) => task && task.status === "DONE");

  if (!doneTasks.length) {
    uiStore.setError("결과서를 생성할 완료된 테스트가 없습니다.");
    return;
  }
  reportAllLoading.value = true;
  try {
    await ezdfsStore.generateReportsForTasks(
      doneTasks.map((task) => task.task_id),
    );
    uiStore.setNotice("ezDFS 결과서 생성이 완료되었습니다.");
  } finally {
    reportAllLoading.value = false;
  }
}

async function executeAll() {
  if (!selectedRules.value.length) {
    uiStore.setError("추가된 Rule이 없습니다.");
    return;
  }

  executeAllLoading.value = true;
  try {
    const created = await ezdfsStore.runAllRules("test");
    const resolved = await ezdfsStore.waitForTasks(
      created.map((task) => task.task_id),
    );
    if (resolved.some((task) => task.status !== "DONE")) {
      uiStore.setError(
        "일부 Rule 테스트가 실패하여 결과서 생성을 중단했습니다.",
      );
      return;
    }
    await ezdfsStore.generateReportsForTasks(
      resolved.map((task) => task.task_id),
    );
    uiStore.setNotice("ezDFS Execute all이 완료되었습니다.");
  } finally {
    executeAllLoading.value = false;
  }
}

async function resetFlow() {
  if (resetFlowLoading.value) {
    return;
  }

  resetFlowLoading.value = true;
  try {
    await ezdfsStore.resetFlow();
    uiStore.setNotice("ezDFS 진행 상태가 초기화되었습니다.");
  } finally {
    resetFlowLoading.value = false;
  }
}
</script>

<template>
  <section class="page-grid">
    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>ezDFS Test Manager</h3>
        <span class="muted">Step {{ currentStep }} / 4</span>
      </div>

      <div class="manager-banner">
        <div class="manager-banner-copy">
          <p class="eyebrow">ezDFS 개발자 Test Flow</p>
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

      <div class="manager-step-strip manager-step-strip-4">
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

      <section class="rtd-manager-layout">
        <div class="manager-workspace">
          <div v-if="currentStep === 1" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 1</p>
                <h4>타겟 서버 선택</h4>
              </div>
            </div>

            <div class="choice-grid choice-grid-inline">
              <button
                v-for="item in modules"
                :key="item"
                class="choice-card"
                :data-selected="selectedModule === item"
                @click="chooseModule(item)"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div v-else-if="currentStep === 2" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 2</p>
                <h4>Rule 선택</h4>
              </div>
            </div>

            <div class="rule-builder-card rule-toolbar-card">
              <div class="rule-builder-row rule-toolbar-row">
                <label class="field rule-builder-field">
                  <span>1. Rule 선택</span>
                  <select
                    :value="selectedRuleFileName"
                    @change="chooseRule($event.target.value)"
                  >
                    <option disabled value="">선택</option>
                    <option
                      v-for="item in rules"
                      :key="item.file_name"
                      :value="item.file_name"
                    >
                      {{ item.rule_name }}
                    </option>
                  </select>
                </label>
                <div class="field rule-builder-field">
                  <span>2. New Version</span>
                  <div class="field-static-value">
                    {{ selectedRuleVersion || "선택" }}
                  </div>
                </div>
                <div class="field rule-builder-field">
                  <span>3. Old Version</span>
                  <div class="field-static-value">
                    {{ selectedRuleOldVersion || "없음" }}
                  </div>
                </div>
                <div class="field rule-builder-action">
                  <span>&nbsp;</span>
                  <button class="button button-primary" @click="addRule">
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
                    >{{ selectedRules.length }} Items</span
                  >
                </div>
              </div>
            </div>

            <div
              v-if="selectedRules.length"
              class="stack-list selection-tray-list"
            >
              <div
                v-for="(item, index) in selectedRules"
                :key="item.file_name"
                class="stack-item rule-target-item selection-tray-item"
              >
                <div class="rule-target-copy">
                  <strong>{{ item.rule_name }}</strong>
                  <p class="muted">New: {{ item.version }}</p>
                  <p class="muted">|</p>
                  <p class="muted">Old: {{ item.old_version || "없음" }}</p>
                </div>
                <button class="button button-ghost" @click="removeRule(index)">
                  제거
                </button>
              </div>
            </div>
            <p v-else class="muted">아직 추가된 테스트 대상 Rule이 없습니다.</p>
          </div>

          <div v-else-if="currentStep === 3" class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 3</p>
                <h4>Sub Rule 확인</h4>
              </div>
            </div>

            <div class="macro-toolbar">
              <button
                class="button button-primary manager-inline-action"
                type="button"
                :disabled="subRuleSearchLoading || !selectedRule"
                @click="searchSubRules"
              >
                <span
                  v-if="subRuleSearchLoading"
                  class="monitor-action-spinner manager-inline-spinner"
                ></span>
                <span>{{ subRuleSearchLoading ? "탐색중" : "탐색" }}</span>
              </button>
            </div>

            <div v-if="subRuleError" class="stack-list">
              <div class="stack-item">
                <strong>조회 실패</strong>
                <span>{{ subRuleError }}</span>
              </div>
            </div>

            <div
              v-else-if="subRulesSearched && subRules.length"
              class="panel-subcard macro-console-card"
            >
              <div class="panel-head">
                <div class="macro-card-head-copy">
                  <h4>Sub Rule List</h4>
                  <span class="pill pill-ghost"
                    >{{ selectedSubRules.length }}/{{
                      subRules.length
                    }}
                    Selected</span
                  >
                </div>
                <div class="macro-card-actions">
                  <button
                    class="button button-ghost macro-card-action"
                    @click="selectAllSubRules"
                  >
                    전체선택
                  </button>
                  <button
                    class="button button-ghost macro-card-action"
                    @click="clearAllSubRules"
                  >
                    전체 해제
                  </button>
                </div>
              </div>
              <div class="stack-list macro-stack-list">
                <div
                  v-for="item in subRules"
                  :key="item"
                  class="stack-item macro-select-item"
                >
                  <span class="macro-select-label">{{ item }}</span>
                  <label class="macro-check">
                    <input
                      :checked="selectedSubRules.includes(item)"
                      type="checkbox"
                      @change="toggleSubRule(item, $event.target.checked)"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div
              v-else-if="subRulesSearched"
              class="stack-list selection-tray-list"
            >
              <p v-if="!subRules.length" class="muted">
                표시할 Sub Rule이 없습니다.
              </p>
            </div>
          </div>

          <div v-else class="wizard-block">
            <div class="manager-section-head">
              <div>
                <p class="eyebrow">Step 4</p>
                <h4>Test 실행</h4>
              </div>
            </div>

            <div class="operation-console">
              <div class="operation-console-main">
                <div class="operation-process-head">
                  <p class="eyebrow">Process all</p>
                </div>
                <div class="operation-process-rail">
                  <div class="operation-process-sequence">
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-1"
                        :disabled="testAllLoading || executeAllLoading"
                        @click="runTest"
                      >
                        <strong>{{
                          testAllLoading ? "Testing..." : "테스트"
                        }}</strong>
                      </button>
                    </div>
                    <span class="operation-process-arrow" aria-hidden="true"
                      >→</span
                    >
                    <div class="operation-process-step">
                      <button
                        class="button operation-button operation-button-step-2"
                        :disabled="reportAllLoading || executeAllLoading"
                        @click="generateReport"
                      >
                        <strong>{{
                          reportAllLoading ? "Generating..." : "결과서 생성"
                        }}</strong>
                      </button>
                    </div>
                  </div>
                  <div
                    class="operation-process-divider"
                    aria-hidden="true"
                  ></div>
                  <div class="operation-process-execute">
                    <button
                      class="button button-primary operation-button operation-button-execute-all"
                      :disabled="executeAllLoading"
                      @click="executeAll"
                    >
                      <strong>{{
                        executeAllLoading ? "Executing..." : "Execute all"
                      }}</strong>
                    </button>
                  </div>
                </div>
              </div>
              <div class="operation-console-side svn-upload-inline-panel">
                <div class="operation-process-head">
                  <p class="eyebrow">SVN Upload</p>
                </div>
                <form class="svn-upload-inline-row" @submit.prevent="submitSvnUpload">
                  <label class="svn-upload-inline-field">
                    <span class="svn-upload-inline-label">AD 계정</span>
                    <input
                      v-model="svnForm.adUser"
                      type="text"
                      autocomplete="username"
                    />
                  </label>
                  <label class="svn-upload-inline-field">
                    <span class="svn-upload-inline-label">PW</span>
                    <input
                      v-model="svnForm.adPassword"
                      type="password"
                      autocomplete="current-password"
                    />
                  </label>
                  <div class="svn-upload-inline-action">
                    <button
                      class="button button-primary"
                      type="submit"
                      :disabled="svnUploading || !selectedRules.length"
                    >
                      {{ svnUploading ? "Uploading..." : "Upload" }}
                    </button>
                  </div>
                  <label class="svn-upload-inline-field svn-upload-inline-result">
                    <span class="svn-upload-inline-label">SVN No.</span>
                    <input :value="svnForm.svnNo" type="text" readonly />
                  </label>
                  <div class="svn-upload-inline-action">
                    <button
                      class="button button-ghost"
                      type="button"
                      :disabled="!svnForm.svnNo"
                      @click="showSvnResult"
                    >
                      Result
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div class="task-grid compact-grid ezdfs-rule-board">
              <div
                v-for="item in ruleTaskCards"
                :key="item.file_name"
                class="task-card ezdfs-rule-card"
              >
                <div class="task-head">
                  <strong>{{ item.rule_name }}</strong>
                  <StatusBadge :status="item.task?.status || 'IDLE'" />
                </div>
                <p class="muted">New Version : {{ item.version }}</p>
                <p class="muted">
                  Old Version : {{ item.old_version || "없음" }}
                </p>
                <label class="field ezdfs-major-change-field">
                  <span>주요 변경 항목</span>
                  <textarea
                    rows="3"
                    :value="majorChangeItems[item.rule_name] || ''"
                    placeholder="변경 항목을 입력하세요"
                    @input="
                      updateMajorChange(item.rule_name, $event.target.value)
                    "
                  ></textarea>
                </label>
                <p class="muted">
                  {{ item.task?.message || "아직 실행된 테스트가 없습니다." }}
                </p>
                <div class="task-actions">
                  <button
                    class="button button-primary"
                    @click="runRuleTest(item)"
                  >
                    Test
                  </button>
                  <button
                    class="button button-ghost"
                    :disabled="!item.task?.raw_result_ready"
                    @click="downloadRaw(item.task)"
                  >
                    Raw Data
                  </button>
                </div>
              </div>
              <p v-if="!ruleTaskCards.length" class="muted">
                추가된 ezDFS Rule이 없습니다.
              </p>
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
              v-if="currentStep < 4"
              class="button button-primary"
              @click="nextStep"
            >
              다음
            </button>
            <button
              v-else
              class="button button-primary"
              :disabled="resetFlowLoading"
              @click="resetFlow"
            >
              {{ resetFlowLoading ? "초기화 중..." : "초기화" }}
            </button>
          </div>
        </div>
      </section>
    </article>
  </section>

  <Teleport to="body">
    <div v-if="svnResultVisible" class="svn-result-overlay" @click.self="closeSvnResult">
      <div class="svn-result-dialog">
        <div class="svn-result-header">
          <h4>SVN Checkin Result</h4>
          <button class="button button-ghost" type="button" @click="closeSvnResult">✕</button>
        </div>
        <pre class="svn-result-body">{{ svnResultText }}</pre>
      </div>
    </div>
  </Teleport>
</template>
