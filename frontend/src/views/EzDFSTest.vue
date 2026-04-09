<template>
  <div class="ezdfs-container">
    <header class="header">
      <div>
        <p class="eyebrow">Distributed FS</p>
        <h2>ezDFS Test</h2>
      </div>
      <button class="ghost" @click="resetSession">세션 초기화</button>
    </header>

    <div class="panel">
      <div class="form-group">
        <div class="row-between">
          <label>타겟 서버 선택</label>
          <button class="small-btn" @click="addTarget">+ 타겟 서버 추가</button>
        </div>
        <div class="target-grid">
          <div class="target-card" v-for="target in targets" :key="target.id">
            <select v-model="target.module_name" @change="(e) => onServerChange(target, e.target.value)">
              <option disabled value="">서버 선택</option>
              <option v-for="s in servers" :key="s.module_name" :value="s.module_name">{{ s.module_name }}:{{ s.port_num }}</option>
            </select>
            <select v-model="target.rule_name" :disabled="!target.module_name">
              <option disabled value="">Rule 선택</option>
              <option v-for="r in (ruleOptions[target.module_name] || [])" :key="r" :value="r">{{ r }}</option>
            </select>
            <div class="card-actions">
              <button class="tiny" @click="useFavorite(target)">⭐ 즐겨찾기 적용</button>
              <button class="tiny" :disabled="!target.rule_name" @click="saveFavorite(target)">즐겨찾기 저장</button>
              <button class="tiny danger" @click="removeTarget(target.id)" v-if="targets.length > 1">삭제</button>
            </div>
          </div>
        </div>
      </div>

      <div class="favorites" v-if="favorites.length">
        <h4>즐겨찾기 Rule</h4>
        <div class="tags">
          <span v-for="f in favorites" :key="f" class="tag">{{ f }}</span>
        </div>
        <p class="muted">즐겨찾기를 클릭하면 현재 선택한 타겟 카드에 적용됩니다.</p>
      </div>

      <button @click="runTest" :disabled="!canRun || isRunning" class="primary run-btn">
        {{ isRunning ? '테스트 진행 중...' : 'Test.jar 수행' }}
      </button>

      <div v-if="targetStatuses.length" class="status-table">
        <div v-for="status in targetStatuses" :key="status.module_name" class="status-row">
          <div>
            <p class="title">{{ status.module_name }}</p>
            <p class="muted">Progress {{ status.progress }}%</p>
          </div>
          <span :class="['badge', status.status.toLowerCase()]">{{ status.status }}</span>
        </div>
      </div>

      <div class="result-panel" v-if="isComplete">
        <h3>결과 다운로드</h3>
        <div class="download-grid">
          <button v-for="status in targetStatuses" :key="status.module_name" @click="downloadRaw(status.module_name)">
            {{ status.module_name }} Raw
          </button>
        </div>
        <div class="summary-section">
          <textarea v-model="summaryText" placeholder="전후 변경점을 입력하세요"></textarea>
          <button @click="createSummary" :disabled="!summaryText">종합 결과 생성/다운로드</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import api from '../api';

const servers = ref([]);
const favorites = ref([]);
const ruleOptions = reactive({});
const targets = ref([{ id: Date.now(), module_name: '', rule_name: '' }]);
const targetStatuses = ref([]);
const taskId = ref(null);
const summaryText = ref('');
const isRunning = ref(false);

const canRun = computed(() => targets.value.some((t) => t.module_name && t.rule_name));
const isComplete = computed(() => targetStatuses.value.length > 0 && targetStatuses.value.every((t) => t.status === 'SUCCESS'));

const saveSession = async () => {
  await api.put('/ezdfs/session', {
    targets: targets.value,
    summaryText: summaryText.value,
  });
};

const loadSession = async () => {
  const res = await api.get('/ezdfs/session');
  if (Object.keys(res.data).length === 0) return;
  targets.value = res.data.targets?.length ? res.data.targets : targets.value;
  summaryText.value = res.data.summaryText || '';
};

const fetchServers = async () => {
  const res = await api.get('/ezdfs/servers');
  servers.value = res.data;
};

const fetchFavorites = async () => {
  const favRes = await api.get('/ezdfs/favorites');
  favorites.value = favRes.data;
};

const fetchRules = async (moduleName) => {
  if (!moduleName) return;
  const res = await api.get('/ezdfs/rules', { params: { module_name: moduleName } });
  ruleOptions[moduleName] = res.data;
};

const onServerChange = async (target, moduleName) => {
  target.rule_name = '';
  await fetchRules(moduleName);
  await saveSession();
};

const addTarget = () => {
  targets.value.push({ id: Date.now() + targets.value.length, module_name: '', rule_name: '' });
};

const removeTarget = (id) => {
  targets.value = targets.value.filter((t) => t.id !== id);
  saveSession();
};

const saveFavorite = async (target) => {
  await api.put('/ezdfs/favorites', null, {
    params: { rule_name: target.rule_name, module_name: target.module_name },
  });
  if (!favorites.value.includes(target.rule_name)) favorites.value.push(target.rule_name);
};

const useFavorite = (target) => {
  if (!favorites.value.length) return;
  target.rule_name = favorites.value[0];
  saveSession();
};

const runTest = async () => {
  try {
    isRunning.value = true;
    const payload = {
      targets: targets.value.filter((t) => t.module_name && t.rule_name).map((t) => ({
        module_name: t.module_name,
        rule_name: t.rule_name,
      })),
    };
    const res = await api.post('/ezdfs/test/start', payload);
    taskId.value = res.data.task_id;
    targetStatuses.value = res.data.target_statuses || [];
    pollStatus();
    await saveSession();
  } catch (e) {
    alert(e.response?.data?.detail || '테스트 시작에 실패했습니다.');
    isRunning.value = false;
  }
};

const pollStatus = () => {
  const interval = setInterval(async () => {
    try {
      const res = await api.get(`/ezdfs/test/status/${taskId.value}`);
      targetStatuses.value = res.data.target_statuses || [];
      if (res.data.status === 'SUCCESS') {
        clearInterval(interval);
        isRunning.value = false;
      }
    } catch (e) {
      clearInterval(interval);
      isRunning.value = false;
    }
  }, 1000);
};

const downloadRaw = async (moduleName) => {
  const res = await api.get(`/ezdfs/test/${taskId.value}/result/raw`, { params: { module_name: moduleName } });
  alert(`Downloading: ${res.data.file_path}`);
};

const createSummary = async () => {
  const res = await api.post(`/ezdfs/test/${taskId.value}/result/summary`, null, {
    params: { summary_text: summaryText.value },
  });
  alert(`Summary Created: ${res.data.file_path}`);
};

const resetSession = async () => {
  await api.delete('/ezdfs/session');
  targets.value = [{ id: Date.now(), module_name: '', rule_name: '' }];
  targetStatuses.value = [];
  summaryText.value = '';
  taskId.value = null;
};

onMounted(async () => {
  await fetchServers();
  await fetchFavorites();
  await loadSession();
  await Promise.all(targets.value.map((t) => fetchRules(t.module_name)));
});

watch(targets, saveSession, { deep: true });
watch(summaryText, saveSession);
</script>

<style scoped>
.ezdfs-container {
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
.panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.target-grid {
  display: grid;
  gap: 0.75rem;
}
.target-card {
  border: 1px solid #444;
  border-radius: 10px;
  padding: 0.75rem;
  display: grid;
  gap: 0.5rem;
}
select, textarea {
  padding: 0.8rem;
  background: #222;
  color: white;
  border: 1px solid #444;
  border-radius: 8px;
}
.card-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.small-btn {
  width: fit-content;
  font-size: 0.85rem;
  padding: 0.4rem 0.8rem;
}
.tiny {
  font-size: 0.8rem;
  padding: 0.35rem 0.75rem;
}
.tiny.danger {
  background: #3a1a1a;
  border: 1px solid #ef4444;
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
}
.run-btn {
  margin-top: 1rem;
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
.title {
  font-weight: 700;
}
.muted {
  color: #aaa;
  font-size: 0.9rem;
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
.result-panel {
  border: 1px solid #444;
  border-radius: 10px;
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}
.download-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.summary-section {
  display: grid;
  gap: 0.75rem;
}
.ghost {
  background: transparent;
  border: 1px solid #444;
}
textarea {
  min-height: 120px;
}
</style>
