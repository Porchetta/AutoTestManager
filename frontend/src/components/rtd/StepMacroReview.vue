<script setup>
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";

const rtdStore = useRtdStore();
const uiStore = useUiStore();
const {
  selectedLineName,
  selectedRuleTargets,
  selectedMacros,
  macroReview,
} = storeToRefs(rtdStore);

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
                @change="toggleMacroSelection(item, $event.target.checked)"
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
                @change="toggleMacroSelection(item, $event.target.checked)"
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
</template>
