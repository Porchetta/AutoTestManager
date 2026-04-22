<script setup>
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { displayTargetLineName } from "./monitorHelpers";

const rtdStore = useRtdStore();
const { targetLines, targetLineOptions } = storeToRefs(rtdStore);

async function selectAllTargets() {
  targetLines.value = [...targetLineOptions.value];
  rtdStore.syncMonitorRuleSelection();
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function clearAllTargets() {
  targetLines.value = [];
  rtdStore.syncMonitorRuleSelection();
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function updateTargetSelection() {
  rtdStore.syncMonitorRuleSelection();
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}
</script>

<template>
  <div class="wizard-block">
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
</template>
