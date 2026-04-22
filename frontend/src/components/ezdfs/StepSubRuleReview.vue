<script setup>
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useEzdfsStore } from "../../stores/ezdfs";
import { useUiStore } from "../../stores/ui";

const ezdfsStore = useEzdfsStore();
const uiStore = useUiStore();
const {
  selectedRule,
  selectedRules,
  subRulesSearched,
  subRules,
  selectedSubRules,
  subRuleError,
} = storeToRefs(ezdfsStore);

const subRuleSearchLoading = ref(false);

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
</script>

<template>
  <div class="wizard-block">
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
            >{{ selectedSubRules.length }}/{{ subRules.length }}
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
</template>
