<script setup>
import { computed, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../stores/rtd";
import { useUiStore } from "../stores/ui";
import { useTaskPolling } from "../composables/useTaskPolling";
import StepBusinessUnit from "../components/rtd/StepBusinessUnit.vue";
import StepLine from "../components/rtd/StepLine.vue";
import StepRuleSelect from "../components/rtd/StepRuleSelect.vue";
import StepMacroReview from "../components/rtd/StepMacroReview.vue";
import StepTargetLine from "../components/rtd/StepTargetLine.vue";
import StepExecute from "../components/rtd/StepExecute.vue";
import TargetMonitor from "../components/rtd/TargetMonitor.vue";
import SvnResultModal from "../components/SvnResultModal.vue";

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
  svnUpload,
} = storeToRefs(rtdStore);

const steps = [
  "사업부 선택",
  "개발 라인 선택",
  "Rule 선택",
  "Macro 확인",
  "타겟 라인 선택",
  "Test 실행",
];

const svnResultText = ref("");
const svnResultVisible = ref(false);

useTaskPolling(() => {
  rtdStore.refreshTasks();
  rtdStore.refreshMonitor();
});

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
});

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

function showSvnResult() {
  svnResultText.value =
    svnUpload.value?.checkin_output || "SVN Upload 결과가 없습니다.";
  svnResultVisible.value = true;
}

function closeSvnResult() {
  svnResultVisible.value = false;
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
          <StepBusinessUnit v-if="currentStep === 1" />
          <StepLine v-else-if="currentStep === 2" />
          <StepRuleSelect v-else-if="currentStep === 3" />
          <StepMacroReview v-else-if="currentStep === 4" />
          <StepTargetLine v-else-if="currentStep === 5" />
          <StepExecute v-else @show-svn-result="showSvnResult" />

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

    <TargetMonitor />
  </section>

  <SvnResultModal
    :visible="svnResultVisible"
    :text="svnResultText"
    @close="closeSvnResult"
  />
</template>
