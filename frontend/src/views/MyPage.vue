<template>
  <div class="mypage-container">
    <h2>My Page</h2>
    
    <div class="section">
      <h3>Change Password</h3>
      <div class="form-group">
        <input v-model="oldPassword" type="password" placeholder="Old Password" />
        <input v-model="newPassword" type="password" placeholder="New Password" />
        <button @click="changePassword">Update Password</button>
      </div>
    </div>

    <div class="section">
      <h3>Last RTD Test Result</h3>
      <div v-if="lastRtd" class="result-card">
        <p><strong>Task ID:</strong> {{ lastRtd.task_id }}</p>
        <p><strong>Status:</strong> {{ lastRtd.status }}</p>
        <p><strong>Date:</strong> {{ new Date(lastRtd.request_time).toLocaleString() }}</p>
        <button @click="downloadRtd(lastRtd.task_id)">Download Again</button>
      </div>
      <p v-else>No recent tests.</p>
    </div>

    <div class="section">
      <h3>Last ezDFS Test Result</h3>
      <div v-if="lastEzdfs" class="result-card">
        <p><strong>Task ID:</strong> {{ lastEzdfs.task_id }}</p>
        <p><strong>Status:</strong> {{ lastEzdfs.status }}</p>
        <button @click="downloadEzdfs(lastEzdfs.task_id)">Download Again</button>
      </div>
      <p v-else>No recent tests.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const oldPassword = ref('');
const newPassword = ref('');
const lastRtd = ref(null);
const lastEzdfs = ref(null);

onMounted(async () => {
  try {
    const rtdRes = await api.get('/mypage/rtd/last-result');
    if (!rtdRes.data.message) lastRtd.value = rtdRes.data;
    
    const ezRes = await api.get('/mypage/ezdfs/last-result');
    if (!ezRes.data.message) lastEzdfs.value = ezRes.data;
  } catch (e) {
    console.error(e);
  }
});

const changePassword = async () => {
  try {
    await api.put('/auth/password', { old_password: oldPassword.value, new_password: newPassword.value });
    alert('Password updated successfully');
    oldPassword.value = '';
    newPassword.value = '';
  } catch (e) {
    alert('Failed to update password');
  }
};

const downloadRtd = async (taskId) => {
  const res = await api.get(`/rtd/test/${taskId}/result/raw`);
  alert(`Downloading: ${res.data.file_path}`);
};

const downloadEzdfs = async (taskId) => {
  const res = await api.get(`/ezdfs/test/${taskId}/result/raw`);
  alert(`Downloading: ${res.data.file_path}`);
};
</script>

<style scoped>
.mypage-container {
  max-width: 600px;
  margin: 0 auto;
}
.section {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: rgba(255,255,255,0.05);
  border-radius: 12px;
}
.form-group {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
input {
  padding: 0.8rem;
  background: #222;
  border: 1px solid #444;
  color: white;
  border-radius: 8px;
}
.result-card {
  background: #222;
  padding: 1rem;
  border-radius: 8px;
}
</style>
