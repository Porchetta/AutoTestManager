<script setup>
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";

const rtdStore = useRtdStore();
const uiStore = useUiStore();
const { selectedLineName, selectedRuleTargets, macroReview } =
  storeToRefs(rtdStore);

const macroSearchLoading = ref(false);

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
</script>

<template>
  <div class="wizard-block">
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
          </div>
        </div>
        <p v-else class="muted">차이가 있는 New Macro가 없습니다.</p>
      </div>
    </div>
    <p v-if="macroReview.searched && !macroReview.error" class="muted">
      Old/New 버전 간 변경된 Macro 파일이 자동으로 포함됩니다.
    </p>
  </div>
</template>
