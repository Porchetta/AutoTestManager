<script setup>
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";

const rtdStore = useRtdStore();
const { selectedBusinessUnit, businessUnits } = storeToRefs(rtdStore);

async function selectBusinessUnit(item) {
  selectedBusinessUnit.value = item;
  rtdStore.resetAfterBusinessUnit();
  await rtdStore.loadLines();
  await rtdStore.saveSession();
}
</script>

<template>
  <div class="wizard-block">
    <div class="manager-section-head">
      <div>
        <p class="eyebrow">Step 1</p>
        <h4>사업부 선택</h4>
      </div>
    </div>
    <div class="choice-grid choice-grid-inline">
      <button
        v-for="item in businessUnits"
        :key="item"
        class="choice-card"
        :data-selected="selectedBusinessUnit === item"
        @click="selectBusinessUnit(item)"
      >
        {{ item }}
      </button>
    </div>
  </div>
</template>
