<template>
  <div class="rtd-container">
    <h2>RTD Test Execution</h2>
    
    <div class="stepper">
      <div v-for="s in 6" :key="s" :class="['step', { active: step >= s }]">{{ s }}</div>
    </div>

    <div class="wizard-content">
      <!-- Step 1: Business Unit -->
      <div v-if="step === 1" class="step-panel">
        <h3>Step 1: Select Business Unit</h3>
        <select v-model="selectedBusiness" @change="fetchLines">
          <option disabled value="">Select Business Unit</option>
          <option v-for="b in businesses" :key="b" :value="b">{{ b }}</option>
        </select>
        <button @click="nextStep" :disabled="!selectedBusiness">Next</button>
      </div>

      <!-- Step 2: Development Line -->
      <div v-if="step === 2" class="step-panel">
        <h3>Step 2: Select Development Line</h3>
        <select v-model="selectedLine" @change="fetchRules">
          <option disabled value="">Select Line</option>
          <option v-for="l in lines" :key="l" :value="l">{{ l }}</option>
        </select>
        <div class="actions">
          <button @click="prevStep" class="secondary">Back</button>
          <button @click="nextStep" :disabled="!selectedLine">Next</button>
        </div>
      </div>

      <!-- Step 3: Rule -->
      <div v-if="step === 3" class="step-panel">
        <h3>Step 3: Select Rule</h3>
        <select v-model="selectedRule" @change="fetchVersions">
          <option disabled value="">Select Rule</option>
          <option v-for="r in rules" :key="r" :value="r">{{ r }}</option>
        </select>
        <div class="actions">
          <button @click="prevStep" class="secondary">Back</button>
          <button @click="nextStep" :disabled="!selectedRule">Next</button>
        </div>
      </div>

      <!-- Step 4: Version Check -->
      <div v-if="step === 4" class="step-panel">
        <h3>Step 4: Confirm Versions</h3>
        <div class="info-box">
          <p><strong>Old Version:</strong> {{ versions.old_version }}</p>
          <p><strong>New Version:</strong> {{ versions.new_version }}</p>
        </div>
        <div class="actions">
          <button @click="prevStep" class="secondary">Back</button>
          <button @click="nextStep">Next</button>
        </div>
      </div>

      <!-- Step 5: Target Lines & Execution -->
      <div v-if="step === 5" class="step-panel">
        <h3>Step 5: Select Target Lines & Run</h3>
        <div class="checkbox-group">
          <label><input type="checkbox" @change="toggleAllTargets" :checked="allTargetsSelected" /> Select All</label>
          <div v-for="t in targetLines" :key="t">
            <label><input type="checkbox" :value="t" v-model="selectedTargets" /> {{ t }}</label>
          </div>
        </div>
        <div class="actions">
          <button @click="prevStep" class="secondary">Back</button>
          <button @click="runTest" :disabled="selectedTargets.length === 0 || isRunning" class="primary">
            {{ isRunning ? 'Running...' : 'Run Test' }}
          </button>
        </div>
        <div v-if="isRunning" class="progress-bar">
          <div class="fill" :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <!-- Step 6: Results -->
      <div v-if="step === 6" class="step-panel">
        <h3>Step 6: Test Results</h3>
        <div class="result-actions">
          <button @click="downloadRaw">Download Raw Data</button>
        </div>
        <div class="summary-section">
          <textarea v-model="summaryText" placeholder="Enter change summary..."></textarea>
          <button @click="createSummary" :disabled="!summaryText">Create Summary Report</button>
        </div>
        <button @click="reset" class="secondary">Start New Test</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';

const step = ref(1);
const businesses = ref([]);
const lines = ref([]);
const rules = ref([]);
const targetLines = ref([]);
const versions = ref({});

const selectedBusiness = ref('');
const selectedLine = ref('');
const selectedRule = ref('');
const selectedTargets = ref([]);
const summaryText = ref('');

const taskId = ref(null);
const isRunning = ref(false);
const progress = ref(0);

// Fetch initial data
onMounted(async () => {
  const res = await api.get('/rtd/businesses');
  businesses.value = res.data;
});

const fetchLines = async () => {
  const res = await api.get('/rtd/lines', { params: { business_unit: selectedBusiness.value } });
  lines.value = res.data;
};

const fetchRules = async () => {
  const res = await api.get('/rtd/rules', { params: { development_line: selectedLine.value } });
  rules.value = res.data;
};

const fetchVersions = async () => {
  const res = await api.get(`/rtd/rules/${selectedRule.value}/versions`);
  versions.value = res.data;
  // Also fetch target lines for step 5
  const targetsRes = await api.get('/rtd/target-lines', { params: { business_unit: selectedBusiness.value } });
  targetLines.value = targetsRes.data;
};

const nextStep = () => step.value++;
const prevStep = () => step.value--;

const allTargetsSelected = computed(() => {
  return targetLines.value.length > 0 && selectedTargets.value.length === targetLines.value.length;
});

const toggleAllTargets = (e) => {
  if (e.target.checked) {
    selectedTargets.value = [...targetLines.value];
  } else {
    selectedTargets.value = [];
  }
};

const runTest = async () => {
  isRunning.value = true;
  try {
    const res = await api.post('/rtd/test/start', {
      target_lines: selectedTargets.value,
      rule_id: selectedRule.value
    });
    taskId.value = res.data.task_id;
    pollStatus();
  } catch (e) {
    console.error(e);
    isRunning.value = false;
  }
};

const pollStatus = () => {
  const interval = setInterval(async () => {
    try {
      const res = await api.get(`/rtd/test/status/${taskId.value}`);
      if (res.data.status === 'SUCCESS') {
        clearInterval(interval);
        isRunning.value = false;
        progress.value = 100;
        step.value = 6;
      } else if (res.data.status === 'FAILED') {
        clearInterval(interval);
        isRunning.value = false;
        alert('Test Failed');
      } else {
        progress.value = 50; // Mock progress
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 1000);
};

const downloadRaw = async () => {
  const res = await api.get(`/rtd/test/${taskId.value}/result/raw`);
  alert(`Downloading: ${res.data.file_path}`);
};

const createSummary = async () => {
  const res = await api.post(`/rtd/test/${taskId.value}/result/summary`, null, {
    params: { summary_text: summaryText.value }
  });
  alert(`Summary Created: ${res.data.file_path}`);
};

const reset = () => {
  step.value = 1;
  selectedBusiness.value = '';
  selectedLine.value = '';
  selectedRule.value = '';
  selectedTargets.value = [];
  taskId.value = null;
  summaryText.value = '';
};
</script>

<style scoped>
.rtd-container {
  max-width: 800px;
  margin: 0 auto;
}
.stepper {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2rem;
}
.step {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
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
.progress-bar {
  height: 10px;
  background: #333;
  border-radius: 5px;
  overflow: hidden;
  margin-top: 1rem;
}
.fill {
  height: 100%;
  background: var(--primary-color);
  transition: width 0.3s;
}
</style>
