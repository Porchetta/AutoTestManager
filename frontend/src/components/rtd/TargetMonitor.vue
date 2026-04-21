<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";
import {
  displayTargetLineName,
  monitorActionClass,
  monitorActionDetail,
  monitorActionDisplay,
  monitorActionIconClass,
  monitorDownloadDisplay,
  monitorStatusChip,
  showMonitorSpinner,
} from "./monitorHelpers";

const rtdStore = useRtdStore();
const uiStore = useUiStore();
const {
  selectedLineName,
  selectedRuleTargets,
  monitorItems,
  monitorRuleSelection,
} = storeToRefs(rtdStore);

const resetFlowLoading = ref(false);

const selectedRuleNames = computed(() => [
  ...new Set(
    selectedRuleTargets.value.map((item) => item.rule_name).filter(Boolean),
  ),
]);

const monitorRuleOptions = computed(() => [
  { value: "__ALL__", label: "ALL" },
  ...selectedRuleNames.value.map((ruleName) => ({
    value: ruleName,
    label: ruleName,
  })),
]);

function isDevLineTarget(targetLine) {
  return displayTargetLineName(targetLine) === selectedLineName.value;
}

async function updateMonitorRuleSelection(targetName, selectedRule) {
  monitorRuleSelection.value = {
    ...monitorRuleSelection.value,
    [targetName]: selectedRule || "__ALL__",
  };
  await rtdStore.saveSession();
  await rtdStore.refreshMonitor();
}

async function runSingleAction(action, targetName) {
  if (action === "copy" && isDevLineTarget(targetName)) {
    uiStore.setNotice("개발 라인은 복사 대상에서 제외됩니다.");
    return;
  }
  const selectedRule = monitorRuleSelection.value[targetName] || "__ALL__";
  const items = await rtdStore.executeAction(action, [targetName], selectedRule);
  if (action === "copy" && !items.length) {
    uiStore.setNotice("개발 라인은 복사 대상에서 제외되었습니다.");
    return;
  }
  await rtdStore.refreshMonitor();
  uiStore.setNotice(
    `${displayTargetLineName(targetName)} ${action.toUpperCase()} 요청이 등록되었습니다.`,
  );
}

async function resetFlow() {
  if (resetFlowLoading.value) {
    return;
  }

  resetFlowLoading.value = true;
  try {
    await rtdStore.resetFlow();
    uiStore.setNotice("RTD 진행 상태가 초기화되었습니다.");
  } finally {
    resetFlowLoading.value = false;
  }
}
</script>

<template>
  <article class="panel panel-span-2">
    <div class="panel-head">
      <h3>Target Status Monitor</h3>
      <button
        class="button button-ghost manager-inline-action"
        type="button"
        :disabled="resetFlowLoading"
        @click="resetFlow"
      >
        <span
          v-if="resetFlowLoading"
          class="monitor-action-spinner manager-inline-spinner"
        ></span>
        <span>{{ resetFlowLoading ? "초기화중" : "초기화" }}</span>
      </button>
    </div>
    <div class="task-grid monitor-board">
      <div
        v-for="item in monitorItems"
        :key="item.target_name"
        class="task-card monitor-card"
      >
        <div class="monitor-header">
          <strong class="monitor-line-name">{{
            displayTargetLineName(item.target_name)
          }}</strong>
          <div class="monitor-header-meta">
            <label class="monitor-rule-select">
              <span class="sr-only">실행 대상 Rule 선택</span>
              <select
                :value="monitorRuleSelection[item.target_name] || '__ALL__'"
                @change="
                  updateMonitorRuleSelection(
                    item.target_name,
                    $event.target.value,
                  )
                "
              >
                <option
                  v-for="option in monitorRuleOptions"
                  :key="`${item.target_name}-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
            <span class="monitor-status-chip">{{
              monitorStatusChip(item)
            }}</span>
          </div>
        </div>

        <div class="monitor-action-grid">
          <button
            class="monitor-action-button"
            :class="monitorActionClass(item.copy.status)"
            :title="
              isDevLineTarget(item.target_name)
                ? '개발 라인은 복사 대상이 아닙니다.'
                : monitorActionDetail(item.copy)
            "
            type="button"
            :disabled="isDevLineTarget(item.target_name)"
            @click="runSingleAction('copy', item.target_name)"
          >
            <strong>복사</strong>
            <span class="monitor-action-meta">
              <span
                v-if="monitorActionDisplay(item.copy.status)"
                :class="[
                  'monitor-action-emoji',
                  monitorActionIconClass(item.copy.status),
                ]"
              >
                {{ monitorActionDisplay(item.copy.status) }}
              </span>
              <span
                v-if="showMonitorSpinner(item.copy.status)"
                class="monitor-action-spinner"
              ></span>
            </span>
          </button>

          <button
            class="monitor-action-button"
            :class="monitorActionClass(item.sync?.status)"
            :title="monitorActionDetail(item.sync)"
            type="button"
            @click="runSingleAction('sync', item.target_name)"
          >
            <strong>Sync</strong>
            <span class="monitor-action-meta">
              <span
                v-if="monitorActionDisplay(item.sync?.status)"
                :class="[
                  'monitor-action-emoji',
                  monitorActionIconClass(item.sync?.status),
                ]"
              >
                {{ monitorActionDisplay(item.sync?.status) }}
              </span>
              <span
                v-if="showMonitorSpinner(item.sync?.status)"
                class="monitor-action-spinner"
              ></span>
            </span>
          </button>

          <button
            class="monitor-action-button"
            :class="monitorActionClass(item.compile.status)"
            :title="monitorActionDetail(item.compile)"
            type="button"
            @click="runSingleAction('compile', item.target_name)"
          >
            <strong>컴파일</strong>
            <span class="monitor-action-meta">
              <span
                v-if="monitorActionDisplay(item.compile.status)"
                :class="[
                  'monitor-action-emoji',
                  monitorActionIconClass(item.compile.status),
                ]"
              >
                {{ monitorActionDisplay(item.compile.status) }}
              </span>
              <span
                v-if="showMonitorSpinner(item.compile.status)"
                class="monitor-action-spinner"
              ></span>
            </span>
          </button>

          <button
            class="monitor-action-button"
            :class="monitorActionClass(item.test.status)"
            :title="monitorActionDetail(item.test)"
            type="button"
            @click="runSingleAction('test', item.target_name)"
          >
            <strong>테스트</strong>
            <span class="monitor-action-meta">
              <span
                v-if="monitorActionDisplay(item.test.status)"
                :class="[
                  'monitor-action-emoji',
                  monitorActionIconClass(item.test.status),
                ]"
              >
                {{ monitorActionDisplay(item.test.status) }}
              </span>
              <span
                v-if="showMonitorSpinner(item.test.status)"
                class="monitor-action-spinner"
              ></span>
            </span>
          </button>

          <button
            class="monitor-action-button monitor-download-action"
            :class="{ 'is-disabled': !item.raw_download.enabled }"
            :disabled="!item.raw_download.enabled"
            type="button"
            @click="rtdStore.downloadRaw(item.raw_download.task_id, item.selected_rule)"
          >
            <strong>Raw Data</strong>
            <span class="monitor-action-meta">
              <span class="monitor-action-emoji">
                {{ monitorDownloadDisplay(item.raw_download.enabled) }}
              </span>
            </span>
          </button>
        </div>
      </div>
      <p v-if="!monitorItems.length" class="muted">
        실행 제어에 들어오면 선택된 타겟 라인의 상태가 여기 표시됩니다.
      </p>
    </div>
  </article>
</template>
