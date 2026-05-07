<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import StatusBadge from "../StatusBadge.vue";
import { useEzdfsStore } from "../../stores/ezdfs";
import { useUiStore } from "../../stores/ui";
import SvnUploadForm from "./SvnUploadForm.vue";

const emit = defineEmits(["show-svn-result"]);

const ezdfsStore = useEzdfsStore();
const uiStore = useUiStore();
const {
  selectedModule,
  selectedRules,
  tasks,
  majorChangeItems,
} = storeToRefs(ezdfsStore);

const syncAllLoading = ref(false);
const testAllLoading = ref(false);
const reportAllLoading = ref(false);
const executeAllLoading = ref(false);

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

async function runSync() {
  if (!selectedModule.value || !selectedRules.value.length) {
    uiStore.setError("추가된 Rule이 없습니다.");
    return;
  }
  syncAllLoading.value = true;
  try {
    await ezdfsStore.runAllRules("sync");
    uiStore.setNotice("선택된 Rule 전체 SYNC 요청이 등록되었습니다.");
  } finally {
    syncAllLoading.value = false;
  }
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
    const syncCreated = await ezdfsStore.runAllRules("sync");
    if (syncCreated.length) {
      const syncResolved = await ezdfsStore.waitForTasks(
        syncCreated.map((task) => task.task_id),
      );
      if (syncResolved.some((task) => task.status !== "DONE")) {
        uiStore.setError(
          "Sync 단계에서 실패가 발생해 전체 실행을 중단했습니다.",
        );
        return;
      }
    }

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
</script>

<template>
  <div class="wizard-block">
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
                class="button operation-button operation-button-step-sync"
                :disabled="syncAllLoading || executeAllLoading"
                @click="runSync"
              >
                <strong>{{
                  syncAllLoading ? "Syncing..." : "Sync"
                }}</strong>
              </button>
            </div>
            <span class="operation-process-arrow" aria-hidden="true">→</span>
            <div class="operation-process-step">
              <button
                class="button operation-button operation-button-step-3"
                :disabled="testAllLoading || executeAllLoading"
                @click="runTest"
              >
                <strong>{{
                  testAllLoading ? "Testing..." : "테스트"
                }}</strong>
              </button>
            </div>
            <span class="operation-process-arrow" aria-hidden="true">→</span>
            <div class="operation-process-step">
              <button
                class="button operation-button operation-button-step-4"
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
      <SvnUploadForm @show-result="emit('show-svn-result')" />
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
            @input="updateMajorChange(item.rule_name, $event.target.value)"
          ></textarea>
        </label>
        <p class="muted">
          {{ item.task?.message || "아직 실행된 테스트가 없습니다." }}
        </p>
        <div class="task-actions">
          <button class="button button-primary" @click="runRuleTest(item)">
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
</template>
