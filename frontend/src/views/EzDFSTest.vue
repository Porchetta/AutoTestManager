<template>
  <div class="ezdfs-container">
    <h2>ezDFS Test Execution</h2>
    
    <div class="panel">
      <div class="form-group">
        <label>Target Server</label>
        <select v-model="selectedServer" @change="fetchRules">
          <option disabled value="">Select Server</option>
          <option v-for="s in servers" :key="s.module_name" :value="s.module_name">{{ s.module_name }}:{{ s.port_num }}</option>
        </select>
      </div>

      <div class="form-group" v-if="selectedServer">
        <label>Select Rule</label>
        <select v-model="selectedRule">
          <option disabled value="">Select Rule</option>
          <option v-for="r in rules" :key="r" :value="r">{{ r }}</option>
        </select>
        <button @click="addToFavorites" class="small-btn">⭐ Add to Favorites</button>
      </div>

      <div class="favorites" v-if="favorites.length">
        <h4>Favorites</h4>
        <div class="tags">
          <span v-for="f in favorites" :key="f" @click="useFavorite(f)" class="tag">{{ f }}</span>
        </div>
      </div>

      <button @click="runTest" :disabled="!selectedRule || isRunning" class="primary run-btn">
        {{ isRunning ? 'Running Test...' : 'Run Test' }}
      </button>

      <div v-if="isRunning" class="progress-bar">
        <div class="fill" :style="{ width: progress + '%' }"></div>
      </div>

      <div v-if="resultReady" class="result-panel">
        <h3>Test Complete</h3>
        <button @click="downloadRaw">Download Raw Data</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const servers = ref([]);
const rules = ref([]);
const favorites = ref([]);
const selectedServer = ref('');
const selectedRule = ref('');
const isRunning = ref(false);
const taskId = ref(null);
const progress = ref(0);
const resultReady = ref(false);

onMounted(async () => {
  const res = await api.get('/ezdfs/servers');
  servers.value = res.data;
  const favRes = await api.get('/ezdfs/favorites');
  favorites.value = favRes.data;
});

const fetchRules = async () => {
  const res = await api.get('/ezdfs/rules', { params: { module_name: selectedServer.value } });
  rules.value = res.data;
};

const addToFavorites = async () => {
  if (!selectedRule.value) return;
  await api.put('/ezdfs/favorites', null, {
    params: { rule_name: selectedRule.value, module_name: selectedServer.value }
  });
  favorites.value.push(selectedRule.value);
};

const useFavorite = (rule) => {
  selectedRule.value = rule;
};

const runTest = async () => {
  isRunning.value = true;
  resultReady.value = false;
  try {
    const res = await api.post('/ezdfs/test/start', null, {
      params: { module_name: selectedServer.value, rule_name: selectedRule.value }
    });
    taskId.value = res.data.task_id;
    pollStatus();
  } catch (e) {
    isRunning.value = false;
  }
};

const pollStatus = () => {
  const interval = setInterval(async () => {
    try {
      const res = await api.get(`/ezdfs/test/status/${taskId.value}`);
      if (res.data.status === 'SUCCESS') {
        clearInterval(interval);
        isRunning.value = false;
        progress.value = 100;
        resultReady.value = true;
      } else {
        progress.value = 50;
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 1000);
};

const downloadRaw = async () => {
  const res = await api.get(`/ezdfs/test/${taskId.value}/result/raw`);
  alert(`Downloading: ${res.data.file_path}`);
};
</script>

<style scoped>
.ezdfs-container {
  max-width: 600px;
  margin: 0 auto;
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
select {
  padding: 0.8rem;
  background: #222;
  color: white;
  border: 1px solid #444;
  border-radius: 8px;
}
.small-btn {
  width: fit-content;
  font-size: 0.8rem;
  padding: 0.4rem 0.8rem;
}
.tags {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.tag {
  background: #333;
  padding: 0.4rem 0.8rem;
  border-radius: 16px;
  cursor: pointer;
}
.tag:hover {
  background: var(--primary-color);
}
.run-btn {
  margin-top: 1rem;
}
.progress-bar {
  height: 10px;
  background: #333;
  border-radius: 5px;
  overflow: hidden;
}
.fill {
  height: 100%;
  background: var(--primary-color);
  transition: width 0.3s;
}
</style>
