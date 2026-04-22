<script setup>
import { computed, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import { useEzdfsStore } from "../stores/ezdfs";
import { useUiStore } from "../stores/ui";
import { useTaskPolling } from "../composables/useTaskPolling";
import StepModule from "../components/ezdfs/StepModule.vue";
import StepRuleSelect from "../components/ezdfs/StepRuleSelect.vue";
import StepSubRuleReview from "../components/ezdfs/StepSubRuleReview.vue";
import StepExecute from "../components/ezdfs/StepExecute.vue";
import SvnResultModal from "../components/SvnResultModal.vue";

const ezdfsStore = useEzdfsStore();
const uiStore = useUiStore();

const {
  currentStep,
  selectedModule,
  selectedRuleVersion,
  selectedRuleOldVersion,
  selectedRules,
  subRulesSearched,
  subRules,
  selectedSubRules,
  subRuleError,
  svnUpload,
} = storeToRefs(ezdfsStore);

const steps = ["타겟 서버 선택", "Rule 선택", "Sub Rule 확인", "Test 실행"];
const resetFlowLoading = ref(false);

const svnResultText = ref("");
const svnResultVisible = ref(false);

useTaskPolling(() => {
  ezdfsStore.refreshTasks();
});

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

onMounted(async () => {
  await ezdfsStore.loadInitialData();
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
          <StepModule v-if="currentStep === 1" />
          <StepRuleSelect v-else-if="currentStep === 2" />
          <StepSubRuleReview v-else-if="currentStep === 3" />
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

  <SvnResultModal
    :visible="svnResultVisible"
    :text="svnResultText"
    @close="closeSvnResult"
  />
</template>
