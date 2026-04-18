<script setup>
import { storeToRefs } from "pinia";
import { useEzdfsStore } from "../../stores/ezdfs";
import { useUiStore } from "../../stores/ui";

const ezdfsStore = useEzdfsStore();
const uiStore = useUiStore();
const {
  selectedRule,
  selectedRuleVersion,
  selectedRuleOldVersion,
  selectedRuleFileName,
  selectedRules,
  rules,
} = storeToRefs(ezdfsStore);

async function chooseRule(ruleName) {
  await ezdfsStore.selectRule(ruleName);
}

async function addRule() {
  if (!selectedRule.value) {
    uiStore.setError("Rule을 먼저 선택해주세요.");
    return;
  }

  const added = await ezdfsStore.addSelectedRule();
  if (!added) {
    uiStore.setError("이미 추가된 Rule입니다.");
    return;
  }

  uiStore.setNotice("Rule이 추가되었습니다.");
}

async function removeRule(index) {
  await ezdfsStore.removeSelectedRule(index);
}
</script>

<template>
  <div class="wizard-block">
    <div class="manager-section-head">
      <div>
        <p class="eyebrow">Step 2</p>
        <h4>Rule 선택</h4>
      </div>
    </div>

    <div class="rule-builder-card rule-toolbar-card">
      <div class="rule-builder-row rule-toolbar-row">
        <label class="field rule-builder-field">
          <span>1. Rule 선택</span>
          <select
            :value="selectedRuleFileName"
            @change="chooseRule($event.target.value)"
          >
            <option disabled value="">선택</option>
            <option
              v-for="item in rules"
              :key="item.file_name"
              :value="item.file_name"
            >
              {{ item.rule_name }}
            </option>
          </select>
        </label>
        <div class="field rule-builder-field">
          <span>2. New Version</span>
          <div class="field-static-value">
            {{ selectedRuleVersion || "선택" }}
          </div>
        </div>
        <div class="field rule-builder-field">
          <span>3. Old Version</span>
          <div class="field-static-value">
            {{ selectedRuleOldVersion || "없음" }}
          </div>
        </div>
        <div class="field rule-builder-action">
          <span>&nbsp;</span>
          <button class="button button-primary" @click="addRule">
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
            >{{ selectedRules.length }} Items</span
          >
        </div>
      </div>
    </div>

    <div
      v-if="selectedRules.length"
      class="stack-list selection-tray-list"
    >
      <div
        v-for="(item, index) in selectedRules"
        :key="item.file_name"
        class="stack-item rule-target-item selection-tray-item"
      >
        <div class="rule-target-copy">
          <strong>{{ item.rule_name }}</strong>
          <p class="muted">New: {{ item.version }}</p>
          <p class="muted">|</p>
          <p class="muted">Old: {{ item.old_version || "없음" }}</p>
        </div>
        <button class="button button-ghost" @click="removeRule(index)">
          제거
        </button>
      </div>
    </div>
    <p v-else class="muted">아직 추가된 테스트 대상 Rule이 없습니다.</p>
  </div>
</template>
