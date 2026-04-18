<script setup>
import { storeToRefs } from "pinia";
import { useEzdfsStore } from "../../stores/ezdfs";

const ezdfsStore = useEzdfsStore();
const { selectedModule, modules } = storeToRefs(ezdfsStore);

async function chooseModule(moduleName) {
  await ezdfsStore.selectModule(moduleName);
}
</script>

<template>
  <div class="wizard-block">
    <div class="manager-section-head">
      <div>
        <p class="eyebrow">Step 1</p>
        <h4>타겟 서버 선택</h4>
      </div>
    </div>

    <div class="choice-grid choice-grid-inline">
      <button
        v-for="item in modules"
        :key="item"
        class="choice-card"
        :data-selected="selectedModule === item"
        @click="chooseModule(item)"
      >
        {{ item }}
      </button>
    </div>
  </div>
</template>
