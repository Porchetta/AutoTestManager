<template>
  <div class="admin-container">
    <h2>Admin Dashboard</h2>
    
    <div class="tabs">
      <button :class="{ active: tab === 'users' }" @click="tab = 'users'">User Management</button>
      <button :class="{ active: tab === 'rtd' }" @click="tab = 'rtd'">RTD Config</button>
      <button :class="{ active: tab === 'ezdfs' }" @click="tab = 'ezdfs'">ezDFS Config</button>
    </div>

    <div v-if="tab === 'users'" class="tab-content">
      <h3>Users</h3>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Module</th>
            <th>Admin</th>
            <th>Approved</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.user_id">
            <td>{{ u.user_id }}</td>
            <td>{{ u.module_name }}</td>
            <td>{{ u.is_admin ? 'Yes' : 'No' }}</td>
            <td>{{ u.is_approved ? 'Yes' : 'No' }}</td>
            <td>{{ new Date(u.created).toLocaleString() }}</td>
            <td>
              <button v-if="!u.is_approved" @click="approveUser(u.user_id, true)" class="small-btn">Approve</button>
              <button v-if="u.is_approved" @click="approveUser(u.user_id, false)" class="small-btn warn">Revoke</button>
              <button @click="toggleAdmin(u.user_id, !u.is_admin)" class="small-btn">{{ u.is_admin ? 'Demote' : 'Promote' }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="tab === 'rtd'" class="tab-content">
      <h3>RTD Configurations</h3>
      <!-- Add Config Form -->
      <div class="add-form">
        <input v-model="newRtd.line_name" placeholder="Line Name" />
        <input v-model="newRtd.line_id" placeholder="Line ID" />
        <input v-model="newRtd.business_unit" placeholder="Business Unit" />
        <input v-model="newRtd.home_dir_path" placeholder="Home Dir" />
        <input v-model="newRtd.modifier" placeholder="Modifier" />
        <button @click="addRtdConfig">Add</button>
      </div>
      <ul>
        <li v-for="c in rtdConfigs" :key="c.line_name">
          {{ c.business_unit }} - {{ c.line_name }} [{{ c.line_id }}] ({{ c.home_dir_path }})
          <button @click="deleteRtdConfig(c.line_name)" class="small-btn warn">Delete</button>
        </li>
      </ul>
    </div>

    <div v-if="tab === 'ezdfs'" class="tab-content">
       <h3>ezDFS Configurations</h3>
       <!-- Add Config Form -->
       <div class="add-form">
        <input v-model="newEzdfs.module_name" placeholder="Module Name" />
        <input v-model="newEzdfs.port_num" placeholder="Port" />
        <input v-model="newEzdfs.home_dir_path" placeholder="Home Dir" />
        <input v-model="newEzdfs.modifier" placeholder="Modifier" />
        <button @click="addEzdfsConfig">Add</button>
      </div>
      <ul>
        <li v-for="c in ezdfsConfigs" :key="c.module_name">
          {{ c.module_name }}:{{ c.port_num }} ({{ c.home_dir_path }})
          <button @click="deleteEzdfsConfig(c.module_name)" class="small-btn warn">Delete</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue';
import api from '../api';

const tab = ref('users');
const users = ref([]);
const rtdConfigs = ref([]);
const ezdfsConfigs = ref([]);

const newRtd = reactive({ line_name: '', line_id: '', business_unit: '', home_dir_path: '', modifier: '' });
const newEzdfs = reactive({ module_name: '', port_num: '', home_dir_path: '', modifier: '' });

const loadData = async () => {
  const uRes = await api.get('/admin/users');
  users.value = uRes.data;
  const rRes = await api.get('/admin/rtd/configs');
  rtdConfigs.value = rRes.data;
  const eRes = await api.get('/admin/ezdfs/configs');
  ezdfsConfigs.value = eRes.data;
};

onMounted(loadData);

const approveUser = async (id, status) => {
  await api.put(`/admin/users/${id}/status`, null, { params: { is_approved: status } });
  loadData();
};

const toggleAdmin = async (id, status) => {
  await api.put(`/admin/users/${id}/role`, null, { params: { is_admin: status } });
  loadData();
};

const addRtdConfig = async () => {
  await api.post('/admin/rtd/configs', newRtd);
  loadData();
};

const deleteRtdConfig = async (lineName) => {
  await api.delete(`/admin/rtd/configs/${lineName}`);
  loadData();
};

const addEzdfsConfig = async () => {
  await api.post('/admin/ezdfs/configs', newEzdfs);
  loadData();
};

const deleteEzdfsConfig = async (moduleName) => {
  await api.delete(`/admin/ezdfs/configs/${moduleName}`);
  loadData();
};
</script>

<style scoped>
.admin-container {
  max-width: 900px;
  margin: 0 auto;
}
.tabs {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
}
.tabs button {
  background: transparent;
  border: 1px solid #444;
  color: #888;
}
.tabs button.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}
.tab-content {
  background: rgba(255,255,255,0.05);
  padding: 1.5rem;
  border-radius: 12px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid #444;
}
.small-btn {
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  margin-right: 0.5rem;
}
.warn {
  background: #ff6b6b;
  color: white;
}
.add-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
</style>
