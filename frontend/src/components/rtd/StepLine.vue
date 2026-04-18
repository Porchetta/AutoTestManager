<script setup>
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";

const rtdStore = useRtdStore();
const { selectedLineName, lines } = storeToRefs(rtdStore);

async function selectLine(item) {
  selectedLineName.value = item;
  rtdStore.resetAfterLine();
  await rtdStore.loadRules();
  await rtdStore.saveSession();
}
</script>

<template>
  <div class="wizard-block">
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
        @click="selectLine(item)"
      >
        {{ item }}
      </button>
    </div>
  </div>
</template>
