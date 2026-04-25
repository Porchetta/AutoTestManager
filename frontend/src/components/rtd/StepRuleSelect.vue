<script setup>
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";

const rtdStore = useRtdStore();
const uiStore = useUiStore();
const {
  selectedRuleTargets,
  targetLines,
  rules,
  favoriteRuleNames,
  ruleVersions,
} = storeToRefs(rtdStore);

function isFavoriteRule(name) {
  return favoriteRuleNames.value.includes(name);
}

function ruleOptionLabel(name) {
  return isFavoriteRule(name) ? `★ ${name}` : name;
}

async function toggleFavoriteForCandidate() {
  if (!ruleCandidate.value || ruleCandidate.value === "error") return;
  await rtdStore.toggleRuleFavorite(ruleCandidate.value);
}

const ruleCandidate = ref("");
const ruleCandidateNewVersion = ref("");
const ruleCandidateOldVersion = ref("");

async function selectRuleCandidate() {
  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  if (ruleCandidate.value === "error") {
    return;
  }
  await rtdStore.loadRuleVersions(ruleCandidate.value);
  const versions = rtdStore.ruleVersions;
  if (versions.length >= 1) {
    ruleCandidateNewVersion.value = versions[0];
  }
  if (versions.length >= 2) {
    ruleCandidateOldVersion.value = versions[1];
  }
}

async function addRuleTarget() {
  if (ruleCandidate.value === "error") {
    uiStore.setError(
      "Rule 목록을 가져오지 못했습니다. 개발 서버 연결과 경로를 확인해주세요.",
    );
    return;
  }

  if (
    !ruleCandidate.value ||
    !ruleCandidateNewVersion.value ||
    !ruleCandidateOldVersion.value
  ) {
    uiStore.setError("Rule, New version, Old version을 모두 선택해주세요.");
    return;
  }

  const exists = selectedRuleTargets.value.some(
    (item) =>
      item.rule_name === ruleCandidate.value &&
      item.new_version === ruleCandidateNewVersion.value &&
      item.old_version === ruleCandidateOldVersion.value,
  );

  if (exists) {
    uiStore.setError("이미 추가된 Rule 조합입니다.");
    return;
  }

  selectedRuleTargets.value.push({
    rule_name: ruleCandidate.value,
    new_version: ruleCandidateNewVersion.value,
    old_version: ruleCandidateOldVersion.value,
  });
  rtdStore.resetMacroState();
  targetLines.value = [];
  rtdStore.syncMonitorRuleSelection();
  await rtdStore.saveSession();

  ruleCandidateNewVersion.value = "";
  ruleCandidateOldVersion.value = "";
  uiStore.setNotice(
    `${ruleCandidate.value} Rule이 테스트 대상으로 추가되었습니다.`,
  );
}

async function removeRuleTarget(index) {
  selectedRuleTargets.value.splice(index, 1);
  rtdStore.resetMacroState();
  targetLines.value = [];
  rtdStore.syncMonitorRuleSelection();
  await rtdStore.saveSession();
}

defineExpose({
  reset() {
    ruleCandidate.value = "";
    ruleCandidateNewVersion.value = "";
    ruleCandidateOldVersion.value = "";
  },
});
</script>

<template>
  <div class="wizard-block">
    <div class="manager-section-head">
      <div>
        <p class="eyebrow">Step 3</p>
        <h4>Rule 선택</h4>
      </div>
    </div>
    <div class="rule-builder-card rule-toolbar-card">
      <div class="rule-builder-row rule-toolbar-row">
        <label class="field rule-builder-field">
          <span>1. Rule 선택</span>
          <select v-model="ruleCandidate" @change="selectRuleCandidate()">
            <option disabled value="">선택</option>
            <option v-for="item in rules" :key="item" :value="item">
              {{ ruleOptionLabel(item) }}
            </option>
          </select>
        </label>
        <div class="field rule-builder-action rule-builder-action-icon">
          <span>&nbsp;</span>
          <button
            type="button"
            class="button button-ghost favorite-toggle"
            :class="{ 'is-active': isFavoriteRule(ruleCandidate) }"
            :disabled="!ruleCandidate || ruleCandidate === 'error'"
            :title="
              isFavoriteRule(ruleCandidate)
                ? '즐겨찾기에서 제거'
                : '즐겨찾기에 추가'
            "
            :aria-label="
              isFavoriteRule(ruleCandidate)
                ? '선택한 Rule을 즐겨찾기에서 제거'
                : '선택한 Rule을 즐겨찾기에 추가'
            "
            @click="toggleFavoriteForCandidate"
          >
            {{ isFavoriteRule(ruleCandidate) ? "★" : "☆" }}
          </button>
        </div>
        <label class="field rule-builder-field">
          <span>2. Old version 선택</span>
          <select v-model="ruleCandidateOldVersion">
            <option disabled value="">선택</option>
            <option
              v-for="item in ruleVersions"
              :key="`rule-old-${item}`"
              :value="item"
            >
              {{ item }}
            </option>
          </select>
        </label>
        <label class="field rule-builder-field">
          <span>3. New version 선택</span>
          <select v-model="ruleCandidateNewVersion">
            <option disabled value="">선택</option>
            <option
              v-for="item in ruleVersions"
              :key="`rule-new-${item}`"
              :value="item"
            >
              {{ item }}
            </option>
          </select>
        </label>
        <div class="field rule-builder-action">
          <span>&nbsp;</span>
          <button class="button button-primary" @click="addRuleTarget">
            추가
          </button>
        </div>
      </div>
    </div>

    <div class="manager-section-head manager-section-head-compact">
      <div>
        <p class="eyebrow">Selection Tray</p>
        <div class="manager-section-title-inline">
          <h4>추가된 테스트 대상 Rule</h4>
          <span class="pill pill-ghost"
            >{{ selectedRuleTargets.length }} Items</span
          >
        </div>
      </div>
    </div>

    <div
      class="stack-list selection-tray-list"
      v-if="selectedRuleTargets.length"
    >
      <div
        v-for="(item, index) in selectedRuleTargets"
        :key="`${item.rule_name}-${item.new_version}-${item.old_version}`"
        class="stack-item rule-target-item selection-tray-item"
      >
        <div class="rule-target-copy">
          <strong>{{ item.rule_name }}</strong>
          <p class="muted">
            New: {{ item.new_version }} | Old: {{ item.old_version }}
          </p>
        </div>
        <button class="button button-ghost" @click="removeRuleTarget(index)">
          제거
        </button>
      </div>
    </div>
    <p v-else class="muted">아직 추가된 테스트 대상 Rule이 없습니다.</p>
  </div>
</template>
