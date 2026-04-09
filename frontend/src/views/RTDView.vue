<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import StatusBadge from '../components/StatusBadge.vue'
import { useRtdStore } from '../stores/rtd'
import { useUiStore } from '../stores/ui'

const rtdStore = useRtdStore()
const uiStore = useUiStore()

const {
  currentStep,
  selectedBusinessUnit,
  selectedLineName,
  selectedRules,
  selectedMacros,
  selectedVersions,
  targetLines,
  tasks,
  businessUnits,
  lines,
  rules,
  macros,
  ruleVersions,
  macroVersions,
  targetLineOptions,
} = storeToRefs(rtdStore)

const steps = [
  '사업부 선택',
  '개발 라인 선택',
  'Rule 선택',
  'Macro 선택',
  '버전 선택',
  '타겟 라인 선택',
  'Test Manage',
]

let pollId = null

const canProceed = computed(() => {
  if (currentStep.value === 1) return Boolean(selectedBusinessUnit.value)
  if (currentStep.value === 2) return Boolean(selectedLineName.value)
  if (currentStep.value === 3) return selectedRules.value.length > 0
  if (currentStep.value === 4) return selectedMacros.value.length > 0
  if (currentStep.value === 5) return Object.values(selectedVersions.value).every(Boolean)
  if (currentStep.value === 6) return targetLines.value.length > 0
  return true
})

onMounted(async () => {
  await rtdStore.loadInitialData()
  pollId = window.setInterval(() => {
    rtdStore.refreshTasks()
  }, 3000)
})

onBeforeUnmount(() => {
  if (pollId) window.clearInterval(pollId)
})

async function selectBusinessUnit() {
  rtdStore.resetAfterBusinessUnit()
  await rtdStore.loadLines()
  await rtdStore.saveSession()
}

async function selectLine() {
  rtdStore.resetAfterLine()
  await rtdStore.loadRules()
  await rtdStore.saveSession()
}

async function syncRules() {
  selectedMacros.value = []
  await rtdStore.loadMacrosAndVersions()
  await rtdStore.saveSession()
}

async function syncMacros() {
  await rtdStore.loadMacrosAndVersions()
  await rtdStore.saveSession()
}

async function nextStep() {
  if (!canProceed.value) {
    uiStore.setError('현재 단계의 필수 선택값을 먼저 입력해주세요.')
    return
  }
  if (currentStep.value < 7) currentStep.value += 1
  await rtdStore.saveSession()
}

async function previousStep() {
  if (currentStep.value > 1) currentStep.value -= 1
  await rtdStore.saveSession()
}

async function run(action) {
  if (!targetLines.value.length) {
    uiStore.setError('타겟 라인을 먼저 선택해주세요.')
    return
  }
  await rtdStore.executeAction(action)
  uiStore.setNotice(`${action.toUpperCase()} 요청이 등록되었습니다.`)
}

async function selectAllTargets() {
  targetLines.value = [...targetLineOptions.value]
  await rtdStore.saveSession()
}

async function retestTask(task) {
  await rtdStore.executeAction('retest', [task.target_name])
  uiStore.setNotice(`${task.target_name} 재테스트 요청이 등록되었습니다.`)
}
</script>

<template>
  <section class="page-grid">
    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>RTD Wizard</h3>
        <span class="muted">Step {{ currentStep }} / 7</span>
      </div>
      <div class="step-strip">
        <div v-for="(label, index) in steps" :key="label" class="step-chip" :data-active="currentStep === index + 1">
          <span>{{ index + 1 }}</span>
          <strong>{{ label }}</strong>
        </div>
      </div>

      <div v-if="currentStep === 1" class="wizard-block">
        <h4>사업부 선택</h4>
        <div class="choice-grid">
          <button
            v-for="item in businessUnits"
            :key="item"
            class="choice-card"
            :data-selected="selectedBusinessUnit === item"
            @click="selectedBusinessUnit = item; selectBusinessUnit()"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <div v-else-if="currentStep === 2" class="wizard-block">
        <h4>개발 라인 선택</h4>
        <div class="choice-grid">
          <button
            v-for="item in lines"
            :key="item"
            class="choice-card"
            :data-selected="selectedLineName === item"
            @click="selectedLineName = item; selectLine()"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <div v-else-if="currentStep === 3" class="wizard-block">
        <h4>Rule 선택</h4>
        <div class="check-grid">
          <label v-for="item in rules" :key="item" class="check-card">
            <input v-model="selectedRules" type="checkbox" :value="item" @change="syncRules" />
            <span>{{ item }}</span>
          </label>
        </div>
      </div>

      <div v-else-if="currentStep === 4" class="wizard-block">
        <h4>Macro 선택</h4>
        <div class="check-grid">
          <label v-for="item in macros" :key="item" class="check-card">
            <input v-model="selectedMacros" type="checkbox" :value="item" @change="syncMacros" />
            <span>{{ item }}</span>
          </label>
        </div>
      </div>

      <div v-else-if="currentStep === 5" class="wizard-block">
        <h4>Rule / Macro 버전 선택</h4>
        <div class="field-grid">
          <label class="field">
            <span>Rule Old</span>
            <select v-model="selectedVersions.rule_old" @change="rtdStore.saveSession()">
              <option disabled value="">선택</option>
              <option v-for="item in ruleVersions" :key="`ro-${item}`" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="field">
            <span>Rule New</span>
            <select v-model="selectedVersions.rule_new" @change="rtdStore.saveSession()">
              <option disabled value="">선택</option>
              <option v-for="item in ruleVersions" :key="`rn-${item}`" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="field">
            <span>Macro Old</span>
            <select v-model="selectedVersions.macro_old" @change="rtdStore.saveSession()">
              <option disabled value="">선택</option>
              <option v-for="item in macroVersions" :key="`mo-${item}`" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="field">
            <span>Macro New</span>
            <select v-model="selectedVersions.macro_new" @change="rtdStore.saveSession()">
              <option disabled value="">선택</option>
              <option v-for="item in macroVersions" :key="`mn-${item}`" :value="item">{{ item }}</option>
            </select>
          </label>
        </div>
      </div>

      <div v-else-if="currentStep === 6" class="wizard-block">
        <div class="panel-head">
          <h4>타겟 라인 선택</h4>
          <button class="button button-ghost" @click="selectAllTargets">
            전체 선택
          </button>
        </div>
        <div class="check-grid">
          <label v-for="item in targetLineOptions" :key="item" class="check-card">
            <input v-model="targetLines" type="checkbox" :value="item" @change="rtdStore.saveSession()" />
            <span>{{ item }}</span>
          </label>
        </div>
      </div>

      <div v-else class="wizard-block">
        <div class="panel-head">
          <h4>Test Manage</h4>
          <div class="button-row">
            <button class="button button-primary" @click="run('copy')">복사</button>
            <button class="button button-secondary" @click="run('compile')">컴파일</button>
            <button class="button button-accent" @click="run('test')">테스트 실행</button>
          </div>
        </div>
        <div class="summary-band">
          <span>Business Unit: {{ selectedBusinessUnit }}</span>
          <span>Line: {{ selectedLineName }}</span>
          <span>Target Lines: {{ targetLines.length }}</span>
        </div>
      </div>

      <div class="wizard-actions">
        <button class="button button-ghost" :disabled="currentStep === 1" @click="previousStep">이전</button>
        <button class="button button-primary" :disabled="currentStep === 7" @click="nextStep">다음</button>
      </div>
    </article>

    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>Target Status Monitor</h3>
        <button class="button button-ghost" @click="rtdStore.refreshTasks()">새로고침</button>
      </div>
      <div class="task-grid">
        <div v-for="task in tasks" :key="task.task_id" class="task-card">
          <div class="task-head">
            <strong>{{ task.target_name }}</strong>
            <StatusBadge :status="task.status" />
          </div>
          <p class="muted">Step: {{ task.current_step }}</p>
          <p class="muted">Message: {{ task.message }}</p>
          <div class="button-row">
            <button class="button button-ghost" :disabled="!task.raw_result_ready" @click="rtdStore.downloadRaw(task.task_id)">
              Raw Data
            </button>
            <button class="button button-ghost" @click="retestTask(task)">재테스트</button>
            <button class="button button-secondary" @click="rtdStore.generateSummary(task.task_id)">결과서 생성</button>
            <button
              class="button button-accent"
              :disabled="!task.summary_result_ready"
              @click="rtdStore.downloadSummary(task.task_id)"
            >
              결과서 다운로드
            </button>
          </div>
        </div>
        <p v-if="!tasks.length" class="muted">아직 등록된 RTD 작업이 없습니다.</p>
      </div>
    </article>
  </section>
</template>
