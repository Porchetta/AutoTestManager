<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";
import SvnUploadForm from "./SvnUploadForm.vue";

const emit = defineEmits(["show-svn-result"]);

const rtdStore = useRtdStore();
const uiStore = useUiStore();
const {
  selectedRuleTargets,
  targetLines,
  majorChangeItems,
} = storeToRefs(rtdStore);

const executeAllLoading = ref(false);

const selectedRuleCards = computed(() => {
  const ruleMap = new Map();
  for (const item of selectedRuleTargets.value) {
    const ruleName = String(item?.rule_name || "").trim();
    if (!ruleName || ruleMap.has(ruleName)) continue;
    ruleMap.set(ruleName, {
      rule_name: ruleName,
      new_version: String(item?.new_version || "").trim(),
      old_version: String(item?.old_version || "").trim(),
    });
  }
  return Array.from(ruleMap.values());
});

const selectedRuleNames = computed(() =>
  selectedRuleCards.value.map((item) => item.rule_name),
);

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

async function updateMajorChange(ruleName, value) {
  await rtdStore.updateMajorChangeItem(ruleName, value);
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
        uiStore.setError(
          "복사 단계에서 실패가 발생해 전체 실행을 중단했습니다.",
        );
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
      uiStore.setError(
        "컴파일 단계에서 실패가 발생해 전체 실행을 중단했습니다.",
      );
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
      uiStore.setError(
        "테스트 단계에서 실패가 발생해 전체 실행을 중단했습니다.",
      );
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
</script>

<template>
  <div class="wizard-block">
    <div class="manager-section-head">
      <div>
        <p class="eyebrow">Step 6</p>
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
                @click="run('copy')"
              >
                <strong>복사</strong>
              </button>
            </div>
            <span class="operation-process-arrow" aria-hidden="true">→</span>
            <div class="operation-process-step">
              <button
                class="button operation-button operation-button-step-2"
                @click="run('compile')"
              >
                <strong>컴파일</strong>
              </button>
            </div>
            <span class="operation-process-arrow" aria-hidden="true">→</span>
            <div class="operation-process-step">
              <button
                class="button operation-button operation-button-step-3"
                @click="run('test')"
              >
                <strong>테스트</strong>
              </button>
            </div>
            <span class="operation-process-arrow" aria-hidden="true">→</span>
            <div class="operation-process-step">
              <button
                class="button operation-button operation-button-step-4"
                @click="generateAggregateSummary"
              >
                <strong>결과서 생성</strong>
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
              @click="executeAllProcess"
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

    <div
      v-if="selectedRuleNames.length"
      class="panel-subcard panel-subcard-fit rtd-major-change-panel"
    >
      <div class="task-grid compact-grid ezdfs-rule-board rtd-major-change-board">
        <div
          v-for="item in selectedRuleCards"
          :key="`rtd-major-change-${item.rule_name}`"
          class="task-card ezdfs-rule-card"
        >
          <div class="task-head">
            <strong>{{ item.rule_name }}</strong>
          </div>
          <p class="muted">New Version : {{ item.new_version || "없음" }}</p>
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
        </div>
      </div>
    </div>
  </div>
</template>
