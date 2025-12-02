<template>
  <div class="rtd-container">
    <header class="header">
      <div>
        <p class="eyebrow">Real-Time Decision</p>
        <h2>RTD Test Execution</h2>
      </div>
      <button class="ghost" @click="resetSession">세션 초기화</button>
    </header>

    <div class="stepper">
      <div v-for="s in 7" :key="s" :class="['step', { active: step >= s }]">{{ s }}</div>
    </div>

    <div class="wizard-content">
      <div v-if="step === 1" class="step-panel">
        <h3>1. 사업부 선택</h3>
        <p class="muted">Memory, Foundry, NRD 중에서 선택하세요.</p>
        <select v-model="selectedBusiness" @change="onBusinessChange">
          <option disabled value="">사업부 선택</option>
          <option v-for="b in businesses" :key="b" :value="b">{{ b }}</option>
        </select>
        <button @click="nextStep" :disabled="!selectedBusiness">다음</button>
      </div>

      <div v-if="step === 2" class="step-panel">
        <h3>2. 개발 라인 선택</h3>
        <p class="muted">선택한 사업부의 line id 리스트를 확인하세요.</p>
        <div class="line-grid">
          <label v-for="line in lines" :key="line.line_name" class="line-card">
            <input type="radio" :value="line.line_name" v-model="selectedLine" @change="onLineChange" />
            <div>
              <p class="title">{{ line.line_name }}</p>
              <p class="muted">ID: {{ line.line_id }}</p>
              <p class="muted">home: {{ line.home_dir_path }}</p>
            </div>
          </label>
        </div>
        <div class="actions">
          <button @click="prevStep" class="secondary">이전</button>
          <button @click="nextStep" :disabled="!selectedLine">다음</button>
        </div>
      </div>

      <div v-if="step === 3" class="step-panel">
        <h3>3. Test 대상 Rule 선택</h3>
        <p class="muted">라인의 home_dir_path 기반 Rule 목록</p>
        <select v-model="selectedRule" @change="onRuleChange">
          <option disabled value="">Rule 선택</option>
          <option v-for="r in rules" :key="r" :value="r">{{ r }}</option>
        </select>
        <p v-if="ruleSource" class="muted">Rule Source: {{ ruleSource }}</p>
        <div class="actions">
          <button @click="prevStep" class="secondary">이전</button>
          <button @click="nextStep" :disabled="!selectedRule">다음</button>
        </div>
      </div>

      <div v-if="step === 4" class="step-panel">
        <h3>4. Old/New Rule 버전 확인</h3>
        <div class="info-box">
          <p><strong>Old Version:</strong> {{ versions.old_version }}</p>
          <p><strong>New Version:</strong> {{ versions.new_version }}</p>
        </div>
        <div class="actions">
          <button @click="prevStep" class="secondary">이전</button>
          <button @click="goTargets">타겟 라인 선택</button>
        </div>
      </div>

      <div v-if="step === 5" class="step-panel">
        <h3>5. 타겟 라인 선택</h3>
        <p class="muted">사업부 내 모든 라인에 대해 병렬 테스트를 요청합니다.</p>
        <div class="checkbox-group">
          <label class="select-all">
            <input type="checkbox" @change="toggleAllTargets" :checked="allTargetsSelected" /> 전체선택
          </label>
          <div v-for="t in targetLines" :key="t" class="checkbox-item">
            <label><input type="checkbox" :value="t" v-model="selectedTargets" /> {{ t }}</label>
          </div>
        </div>
        <div class="actions">
          <button @click="prevStep" class="secondary">이전</button>
          <button @click="runTest" :disabled="selectedTargets.length === 0 || hasRunningLines" class="primary">
            {{ hasRunningLines ? '진행 중...' : 'Test 실행' }}
          </button>
        </div>
        <div v-if="lineStatuses.length" class="status-table">
          <div class="status-row" v-for="line in lineStatuses" :key="line.line_name">
            <div>
              <p class="title">{{ line.line_name }}</p>
              <p class="muted">Progress {{ line.progress }}%</p>
            </div>
            <span :class="['badge', line.status.toLowerCase()]">{{ line.status }}</span>
          </div>
        </div>
      </div>

      <div v-if="step === 6" class="step-panel">
        <h3>6. 결과 다운로드 & 종합 결과</h3>
        <div class="result-actions">
          <p class="muted">라인별 Raw Data를 다운로드하세요.</p>
          <div class="download-grid">
            <button
              v-for="line in lineStatuses"
              :key="line.line_name"
              :disabled="line.status !== 'SUCCESS'"
              @click="downloadRaw(line.line_name)"
            >
              {{ line.line_name }} Raw
            </button>
          </div>
        </div>
        <div class="summary-section">
          <textarea v-model="summaryText" placeholder="전후 변경점을 입력하세요"></textarea>
          <button @click="createSummary" :disabled="!canCreateSummary">종합 결과 생성/다운로드</button>
        </div>
        <button class="ghost" @click="step = 7">다음 단계</button>
      </div>

      <div v-if="step === 7" class="step-panel">
        <h3>7. 결과 상시 조회</h3>
        <p class="muted">마지막 요청한 결과는 마이페이지에서 언제든 확인할 수 있습니다.</p>
        <button @click="goMyPage" class="primary">마이페이지로 이동</button>
        <button @click="resetSession" class="secondary">새로운 테스트 시작</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';

const router = useRouter();
const step = ref(1);
const businesses = ref([]);
const lines = ref([]);
const rules = ref([]);
const targetLines = ref([]);
const versions = ref({ old_version: '-', new_version: '-' });

const selectedBusiness = ref('');
const selectedLine = ref('');
const selectedRule = ref('');
const selectedTargets = ref([]);
const summaryText = ref('');
const ruleSource = ref('');

const taskId = ref(null);
const lineStatuses = ref([]);

const allTargetsSelected = computed(() => targetLines.value.length > 0 && selectedTargets.value.length === targetLines.value.length);
const hasRunningLines = computed(() => lineStatuses.value.some((l) => l.status !== 'SUCCESS'));
const canCreateSummary = computed(() => summaryText.value && lineStatuses.value.length > 0 && !hasRunningLines.value);

const saveSession = async () => {
  await api.put('/rtd/session', {
    step: step.value,
    selectedBusiness: selectedBusiness.value,
    selectedLine: selectedLine.value,
    selectedRule: selectedRule.value,
    selectedTargets: selectedTargets.value,
    summaryText: summaryText.value,
  });
};

const loadSession = async () => {
  const res = await api.get('/rtd/session');
  if (Object.keys(res.data).length === 0) return;
  const data = res.data;
  selectedBusiness.value = data.selectedBusiness || '';
  selectedLine.value = data.selectedLine || '';
  selectedRule.value = data.selectedRule || '';
  selectedTargets.value = data.selectedTargets || [];
  summaryText.value = data.summaryText || '';
  step.value = data.step || 1;
};

const fetchBusinesses = async () => {
  const res = await api.get('/rtd/businesses');
  businesses.value = res.data;
};

const fetchLines = async () => {
  if (!selectedBusiness.value) return;
  const res = await api.get('/rtd/lines', { params: { business_unit: selectedBusiness.value } });
  lines.value = res.data;
};

const fetchRules = async () => {
  if (!selectedLine.value) return;
  const res = await api.get('/rtd/rules', { params: { line_name: selectedLine.value } });
  rules.value = res.data.rules;
  ruleSource.value = res.data.home_dir_path;
};

const fetchVersions = async () => {
  if (!selectedRule.value) return;
  const res = await api.get(`/rtd/rules/${selectedRule.value}/versions`);
  versions.value = res.data;
  const targetsRes = await api.get('/rtd/target-lines', { params: { business_unit: selectedBusiness.value } });
  targetLines.value = targetsRes.data;
};

const onBusinessChange = async () => {
  restartFromStep(1);
  await fetchLines();
  await saveSession();
};

const onLineChange = async () => {
  restartFromStep(2);
  await fetchRules();
  await saveSession();
};

const onRuleChange = async () => {
  restartFromStep(3);
  await fetchVersions();
  await saveSession();
};

const restartFromStep = (nextStep) => {
  step.value = nextStep;
  if (nextStep <= 2) {
    selectedLine.value = '';
    rules.value = [];
    ruleSource.value = '';
  }
  if (nextStep <= 3) {
    selectedRule.value = '';
    versions.value = { old_version: '-', new_version: '-' };
  }
  if (nextStep <= 4) {
    selectedTargets.value = [];
    lineStatuses.value = [];
    taskId.value = null;
  }
  if (nextStep <= 5) {
    summaryText.value = '';
  }
};

const nextStep = () => {
  step.value += 1;
  saveSession();
};
const prevStep = () => {
  step.value -= 1;
  saveSession();
};

const toggleAllTargets = (e) => {
  selectedTargets.value = e.target.checked ? [...targetLines.value] : [];
  saveSession();
};

const runTest = async () => {
  if (selectedTargets.value.length === 0) return;
  try {
    const res = await api.post('/rtd/test/start', {
      target_lines: selectedTargets.value,
      rule_id: selectedRule.value,
    });
    taskId.value = res.data.task_id;
    lineStatuses.value = res.data.line_statuses || [];
    pollStatus();
    step.value = 5;
    await saveSession();
  } catch (e) {
    alert(e.response?.data?.detail || '테스트 시작에 실패했습니다.');
  }
};

const pollStatus = () => {
  const interval = setInterval(async () => {
    try {
      const res = await api.get(`/rtd/test/status/${taskId.value}`);
      lineStatuses.value = res.data.line_statuses || [];
      if (res.data.status === 'SUCCESS') {
        clearInterval(interval);
        step.value = 6;
        await saveSession();
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 1000);
};

const downloadRaw = async (lineName) => {
  const res = await api.get(`/rtd/test/${taskId.value}/result/raw`, { params: { line_name: lineName } });
  alert(`Downloading: ${res.data.file_path}`);
};

const createSummary = async () => {
  const res = await api.post(`/rtd/test/${taskId.value}/result/summary`, null, {
    params: { summary_text: summaryText.value },
  });
  alert(`Summary Created: ${res.data.file_path}`);
  step.value = 7;
  await saveSession();
};

const resetSession = async () => {
  await api.delete('/rtd/session');
  step.value = 1;
  selectedBusiness.value = '';
  selectedLine.value = '';
  selectedRule.value = '';
  selectedTargets.value = [];
  summaryText.value = '';
  lineStatuses.value = [];
  taskId.value = null;
};

const goTargets = () => {
  step.value = 5;
  saveSession();
};

const goMyPage = () => router.push('/mypage');

onMounted(async () => {
  await fetchBusinesses();
  await loadSession();
  await fetchLines();
  await fetchRules();
  await fetchVersions();
});

watch(selectedTargets, saveSession);
watch(summaryText, saveSession);
</script>

<style scoped>
.rtd-container {
  max-width: 900px;
  margin: 0 auto;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: 0.85rem;
  color: var(--primary-color);
}
.stepper {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.5rem;
  margin-bottom: 2rem;
}
.step {
  height: 32px;
  border-radius: 8px;
  background: #333;
  display: grid;
  place-items: center;
  font-weight: bold;
}
.step.active {
  background: var(--primary-color);
}
.step-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
select, textarea {
  padding: 0.8rem;
  background: #222;
  color: white;
  border: 1px solid #444;
  border-radius: 8px;
}
.actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}
.secondary {
  background: #444;
}
.ghost {
  background: transparent;
  border: 1px solid #444;
}
.line-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}
.line-card {
  border: 1px solid #444;
  padding: 0.75rem;
  border-radius: 10px;
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}
.title {
  font-weight: 700;
}
.muted {
  color: #aaa;
  font-size: 0.9rem;
}
.info-box {
  border: 1px solid #444;
  border-radius: 10px;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.04);
}
.checkbox-group {
  display: grid;
  gap: 0.5rem;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.select-all {
  font-weight: 700;
}
.status-table {
  border: 1px solid #444;
  border-radius: 10px;
  padding: 0.75rem;
  display: grid;
  gap: 0.5rem;
}
.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: #1f1f1f;
}
.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-weight: 700;
}
.badge.success {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}
.badge.running,
.badge.pending {
  background: rgba(234, 179, 8, 0.15);
  color: #fbbf24;
}
.result-actions {
  border: 1px solid #444;
  border-radius: 10px;
  padding: 1rem;
}
.download-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
.summary-section {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}
textarea {
  min-height: 120px;
}
</style>
