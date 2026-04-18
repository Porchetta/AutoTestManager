<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDelete, apiGet, apiPost, apiPut } from '../api'
import { useUiStore } from '../stores/ui'

const uiStore = useUiStore()
const activeTab = ref('users')
const selectedUserModule = ref('ALL')
const selectedRtdBusinessUnit = ref('ALL')
const hostSortKey = ref('name')
const hostSortOrder = ref('asc')
const rtdSortKey = ref('line_name')
const rtdSortOrder = ref('asc')
const ezdfsSortKey = ref('module_name')
const ezdfsSortOrder = ref('asc')

const users = ref([])
const hosts = ref([])
const hostSshLimits = ref({})
const hostSshProbeLoading = reactive({})
const rtdConfigs = ref([])
const ezdfsConfigs = ref([])
const userDrafts = reactive({})
const hostDrafts = reactive({})
const rtdDrafts = reactive({})
const ezdfsDrafts = reactive({})

const hostForm = reactive({ name: '', ip: '' })
const rtdForm = reactive({
  line_name: '',
  line_id: '',
  business_unit: '',
  home_dir_path: '',
  host_name: '',
  login_user: '',
})
const ezdfsForm = reactive({
  module_name: '',
  port: 22,
  home_dir_path: '',
  host_name: '',
  login_user: '',
})

const expandedHosts = reactive(new Set())
const credentialDrafts = reactive({})
const credentialForms = reactive({})

const hostOptions = computed(() => hosts.value.map((item) => item.name))
const hostCredentialMap = computed(() => {
  const map = {}
  for (const host of hosts.value) {
    map[host.name] = Array.isArray(host.credentials) ? host.credentials : []
  }
  return map
})
const rtdLoginUserOptions = computed(() =>
  (hostCredentialMap.value[rtdForm.host_name] || []).map((cred) => cred.login_user),
)
const ezdfsLoginUserOptions = computed(() =>
  (hostCredentialMap.value[ezdfsForm.host_name] || []).map((cred) => cred.login_user),
)
function credentialsFor(hostName) {
  return hostCredentialMap.value[hostName] || []
}
function loginUserOptionsFor(hostName) {
  return credentialsFor(hostName).map((cred) => cred.login_user)
}
const userModules = computed(() => {
  const modules = [...new Set(users.value.map((user) => user.module_name).filter(Boolean))]
  return ['ALL', ...modules.sort((a, b) => a.localeCompare(b))]
})
const filteredUsers = computed(() => {
  if (selectedUserModule.value === 'ALL') {
    return users.value
  }
  return users.value.filter((user) => user.module_name === selectedUserModule.value)
})
const rtdBusinessUnits = computed(() => {
  const items = [...new Set(rtdConfigs.value.map((item) => item.business_unit).filter(Boolean))]
  return ['ALL', ...items.sort((a, b) => a.localeCompare(b))]
})
const filteredRtdConfigs = computed(() => {
  const filtered =
    selectedRtdBusinessUnit.value === 'ALL'
      ? [...rtdConfigs.value]
      : rtdConfigs.value.filter((item) => item.business_unit === selectedRtdBusinessUnit.value)

  return sortItems(filtered, rtdSortKey.value, rtdSortOrder.value)
})
const sortedHosts = computed(() => sortItems(hosts.value, hostSortKey.value, hostSortOrder.value))
const sortedEzdfsConfigs = computed(() => sortItems(ezdfsConfigs.value, ezdfsSortKey.value, ezdfsSortOrder.value))

function syncUserDrafts() {
  for (const user of users.value) {
    if (!userDrafts[user.user_id]) {
      userDrafts[user.user_id] = {
        editing: {
          module_name: false,
          is_approved: false,
          is_admin: false,
        },
        values: {
          module_name: user.module_name,
          is_approved: user.is_approved,
          is_admin: user.is_admin,
        },
      }
      continue
    }

    userDrafts[user.user_id].values.module_name = user.module_name
    userDrafts[user.user_id].values.is_approved = user.is_approved
    userDrafts[user.user_id].values.is_admin = user.is_admin
  }
}

function syncHostDrafts() {
  for (const host of hosts.value) {
    hostDrafts[host.name] = {
      editing: hostDrafts[host.name]?.editing ?? false,
      values: {
        name: host.name,
        ip: host.ip,
      },
    }
    syncCredentialDrafts(host)
    if (!credentialForms[host.name]) {
      credentialForms[host.name] = { login_user: '', login_password: '', visible: false }
    }
  }
}

function syncCredentialDrafts(host) {
  const map = credentialDrafts[host.name] || {}
  const nextKeys = new Set()
  for (const cred of host.credentials || []) {
    nextKeys.add(cred.login_user)
    map[cred.login_user] = {
      editing: map[cred.login_user]?.editing ?? false,
      values: {
        login_user: cred.login_user,
        login_password: '',
      },
    }
  }
  for (const key of Object.keys(map)) {
    if (!nextKeys.has(key)) delete map[key]
  }
  credentialDrafts[host.name] = map
}

function hostSshLimitInfo(hostName) {
  return hostSshLimits.value[hostName] || null
}

function hostSshLimitLabel(hostName) {
  const info = hostSshLimitInfo(hostName)
  if (!info) return '-'
  if (info.source === 'unknown') return '-'
  return info.source === 'default' ? `${info.parallel_limit} (default)` : String(info.parallel_limit)
}

function syncRtdDrafts() {
  for (const item of rtdConfigs.value) {
    rtdDrafts[item.line_name] = {
      editing: rtdDrafts[item.line_name]?.editing ?? false,
      values: {
        line_name: item.line_name,
        line_id: item.line_id,
        business_unit: item.business_unit,
        home_dir_path: item.home_dir_path,
        host_name: item.host_name,
        login_user: item.login_user,
      },
    }
  }
}

function syncEzdfsDrafts() {
  for (const item of ezdfsConfigs.value) {
    ezdfsDrafts[item.module_name] = {
      editing: ezdfsDrafts[item.module_name]?.editing ?? false,
      values: {
        module_name: item.module_name,
        port: item.port,
        home_dir_path: item.home_dir_path,
        host_name: item.host_name,
        login_user: item.login_user,
      },
    }
  }
}

function userDraft(user) {
  return userDrafts[user.user_id]
}

function hostDraft(host) {
  return hostDrafts[host.name]
}

function rtdDraft(item) {
  return rtdDrafts[item.line_name]
}

function ezdfsDraft(item) {
  return ezdfsDrafts[item.module_name]
}

function toggleUserEdit(userId, field) {
  userDrafts[userId].editing[field] = !userDrafts[userId].editing[field]
}

function userChanged(user) {
  const draft = userDraft(user)
  if (!draft) return false

  return (
    draft.values.module_name !== user.module_name ||
    draft.values.is_approved !== user.is_approved ||
    draft.values.is_admin !== user.is_admin
  )
}

function isHostEditing(host) {
  return Boolean(hostDraft(host)?.editing)
}

function isRtdEditing(item) {
  return Boolean(rtdDraft(item)?.editing)
}

function isEzdfsEditing(item) {
  return Boolean(ezdfsDraft(item)?.editing)
}

function hostChanged(host) {
  const draft = hostDraft(host)
  if (!draft) return false
  return draft.values.name !== host.name || draft.values.ip !== host.ip
}

function rtdChanged(item) {
  const draft = rtdDraft(item)
  if (!draft) return false
  return (
    draft.values.line_name !== item.line_name ||
    draft.values.line_id !== item.line_id ||
    draft.values.business_unit !== item.business_unit ||
    draft.values.home_dir_path !== item.home_dir_path ||
    draft.values.host_name !== item.host_name ||
    draft.values.login_user !== item.login_user
  )
}

function ezdfsChanged(item) {
  const draft = ezdfsDraft(item)
  if (!draft) return false
  return (
    draft.values.module_name !== item.module_name ||
    Number(draft.values.port) !== Number(item.port) ||
    draft.values.home_dir_path !== item.home_dir_path ||
    draft.values.host_name !== item.host_name ||
    draft.values.login_user !== item.login_user
  )
}

function sortItems(items, sortKey, sortOrder) {
  const direction = sortOrder === 'asc' ? 1 : -1
  return [...items].sort((left, right) => {
    const leftValue = String(left?.[sortKey] ?? '')
    const rightValue = String(right?.[sortKey] ?? '')
    return leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: 'base' }) * direction
  })
}

function toggleHostSort(key) {
  if (hostSortKey.value === key) {
    hostSortOrder.value = hostSortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }
  hostSortKey.value = key
  hostSortOrder.value = 'asc'
}

function toggleRtdSort(key) {
  if (rtdSortKey.value === key) {
    rtdSortOrder.value = rtdSortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }

  rtdSortKey.value = key
  rtdSortOrder.value = 'asc'
}

function toggleEzdfsSort(key) {
  if (ezdfsSortKey.value === key) {
    ezdfsSortOrder.value = ezdfsSortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }
  ezdfsSortKey.value = key
  ezdfsSortOrder.value = 'asc'
}

function sortState(activeKey, activeOrder, key) {
  return {
    active: activeKey === key,
    ascending: activeKey === key && activeOrder === 'asc',
    descending: activeKey === key && activeOrder === 'desc',
  }
}

async function loadAll() {
  users.value = (await apiGet('/api/admin/users')).items
  hosts.value = (await apiGet('/api/admin/hosts')).items
  hostSshLimits.value = Object.fromEntries(
    ((await apiGet('/api/admin/hosts/ssh-limits')).items || []).map((item) => [item.host_name, item]),
  )
  rtdConfigs.value = (await apiGet('/api/admin/rtd/configs')).items
  ezdfsConfigs.value = (await apiGet('/api/admin/ezdfs/configs')).items
  syncUserDrafts()
  syncHostDrafts()
  syncRtdDrafts()
  syncEzdfsDrafts()
}

async function probeHostSshLimit(hostName) {
  if (hostSshProbeLoading[hostName]) return
  hostSshProbeLoading[hostName] = true
  try {
    const result = await apiPost(`/api/admin/hosts/${hostName}/ssh-limits/probe`, {})
    hostSshLimits.value = {
      ...hostSshLimits.value,
      [hostName]: result.item,
    }
    uiStore.setNotice(`${hostName} SSH Limit 감지가 완료되었습니다.`)
  } finally {
    hostSshProbeLoading[hostName] = false
  }
}

onMounted(loadAll)

async function approveUser(userId) {
  await apiPut(`/api/admin/users/${userId}/approve`, {})
  await loadAll()
}

async function rejectUser(userId) {
  await apiPut(`/api/admin/users/${userId}/reject`, {})
  await loadAll()
}

async function toggleAdmin(user) {
  await apiPut(`/api/admin/users/${user.user_id}/role`, { is_admin: !user.is_admin })
  await loadAll()
}

async function removeUser(userId) {
  if (!(await uiStore.confirmAction('이 사용자를 삭제하시겠습니까?', { title: '사용자 삭제' }))) return
  await apiDelete(`/api/admin/users/${userId}`)
  await loadAll()
}

async function applyUser(user) {
  const draft = userDraft(user)
  await apiPut(`/api/admin/users/${user.user_id}`, {
    module_name: draft.values.module_name,
    is_approved: draft.values.is_approved,
    is_admin: draft.values.is_admin,
  })
  draft.editing.module_name = false
  draft.editing.is_approved = false
  draft.editing.is_admin = false
  await loadAll()
  uiStore.setNotice(`${user.user_id} 정보가 반영되었습니다.`)
}

async function createHost() {
  await apiPost('/api/admin/hosts', hostForm)
  Object.assign(hostForm, { name: '', ip: '' })
  await loadAll()
}

function toggleHostEdit(host) {
  hostDrafts[host.name].editing = !hostDrafts[host.name].editing
}

function cancelHostEdit(host) {
  hostDrafts[host.name] = {
    editing: false,
    values: { name: host.name, ip: host.ip },
  }
}

async function updateHost(host) {
  const draft = hostDraft(host)
  await apiPut(`/api/admin/hosts/${host.name}`, draft.values)
  draft.editing = false
  await loadAll()
  uiStore.setNotice(`${draft.values.name} host 정보가 반영되었습니다.`)
}

async function deleteHost(name) {
  if (!(await uiStore.confirmAction('이 host를 삭제하시겠습니까?', { title: 'Host 삭제' }))) return
  await apiDelete(`/api/admin/hosts/${name}`)
  await loadAll()
}

function isHostExpanded(hostName) {
  return expandedHosts.has(hostName)
}

function toggleHostExpand(hostName) {
  if (expandedHosts.has(hostName)) {
    expandedHosts.delete(hostName)
  } else {
    expandedHosts.add(hostName)
  }
}

function credentialForm(hostName) {
  if (!credentialForms[hostName]) {
    credentialForms[hostName] = { login_user: '', login_password: '', visible: false }
  }
  return credentialForms[hostName]
}

function showCredentialForm(hostName) {
  credentialForm(hostName).visible = true
}

function cancelCredentialForm(hostName) {
  credentialForms[hostName] = { login_user: '', login_password: '', visible: false }
}

async function addCredential(hostName) {
  const form = credentialForm(hostName)
  if (!form.login_user.trim() || !form.login_password) {
    uiStore.setNotice('login_user와 password를 입력하세요.')
    return
  }
  await apiPost(`/api/admin/hosts/${hostName}/credentials`, {
    login_user: form.login_user.trim(),
    login_password: form.login_password,
  })
  cancelCredentialForm(hostName)
  await loadAll()
  uiStore.setNotice(`${hostName}에 credential이 추가되었습니다.`)
}

function credentialDraft(hostName, loginUser) {
  return credentialDrafts[hostName]?.[loginUser]
}

function isCredentialEditing(hostName, loginUser) {
  return Boolean(credentialDraft(hostName, loginUser)?.editing)
}

function toggleCredentialEdit(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser)
  if (!draft) return
  draft.editing = !draft.editing
  if (!draft.editing) {
    draft.values = { login_user: loginUser, login_password: '' }
  }
}

function cancelCredentialEdit(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser)
  if (!draft) return
  draft.editing = false
  draft.values = { login_user: loginUser, login_password: '' }
}

async function updateCredential(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser)
  if (!draft) return
  const payload = {
    login_user: draft.values.login_user.trim(),
  }
  if (draft.values.login_password) {
    payload.login_password = draft.values.login_password
  }
  await apiPut(`/api/admin/hosts/${hostName}/credentials/${encodeURIComponent(loginUser)}`, payload)
  await loadAll()
  uiStore.setNotice(`${hostName}/${loginUser} credential이 수정되었습니다.`)
}

async function deleteCredential(hostName, loginUser) {
  if (!(await uiStore.confirmAction(`${loginUser} credential을 삭제하시겠습니까?`, { title: 'Credential 삭제' })))
    return
  await apiDelete(`/api/admin/hosts/${hostName}/credentials/${encodeURIComponent(loginUser)}`)
  await loadAll()
}

function onRtdFormHostChange() {
  const options = loginUserOptionsFor(rtdForm.host_name)
  if (!options.includes(rtdForm.login_user)) rtdForm.login_user = ''
}

function onEzdfsFormHostChange() {
  const options = loginUserOptionsFor(ezdfsForm.host_name)
  if (!options.includes(ezdfsForm.login_user)) ezdfsForm.login_user = ''
}

function onRtdDraftHostChange(item) {
  const draft = rtdDraft(item)
  if (!draft) return
  const options = loginUserOptionsFor(draft.values.host_name)
  if (!options.includes(draft.values.login_user)) draft.values.login_user = ''
}

function onEzdfsDraftHostChange(item) {
  const draft = ezdfsDraft(item)
  if (!draft) return
  const options = loginUserOptionsFor(draft.values.host_name)
  if (!options.includes(draft.values.login_user)) draft.values.login_user = ''
}

async function createRtdConfig() {
  await apiPost('/api/admin/rtd/configs', rtdForm)
  Object.assign(rtdForm, {
    line_name: '',
    line_id: '',
    business_unit: '',
    home_dir_path: '',
    host_name: '',
    login_user: '',
  })
  await loadAll()
}

function toggleRtdEdit(item) {
  rtdDrafts[item.line_name].editing = !rtdDrafts[item.line_name].editing
}

function cancelRtdEdit(item) {
  rtdDrafts[item.line_name] = {
    editing: false,
    values: {
      line_name: item.line_name,
      line_id: item.line_id,
      business_unit: item.business_unit,
      home_dir_path: item.home_dir_path,
      host_name: item.host_name,
      login_user: item.login_user,
    },
  }
}

async function updateRtd(item) {
  const draft = rtdDraft(item)
  await apiPut(`/api/admin/rtd/configs/${item.line_name}`, draft.values)
  draft.editing = false
  await loadAll()
  uiStore.setNotice(`${draft.values.line_name} RTD 설정이 반영되었습니다.`)
}

async function deleteRtd(lineName) {
  if (!(await uiStore.confirmAction('정말 삭제하시겠습니까?', { title: 'RTD 설정 삭제' }))) return
  await apiDelete(`/api/admin/rtd/configs/${lineName}`)
  await loadAll()
}

async function createEzdfsConfig() {
  await apiPost('/api/admin/ezdfs/configs', ezdfsForm)
  Object.assign(ezdfsForm, {
    module_name: '',
    port: 22,
    home_dir_path: '',
    host_name: '',
    login_user: '',
  })
  await loadAll()
}

function toggleEzdfsEdit(item) {
  ezdfsDrafts[item.module_name].editing = !ezdfsDrafts[item.module_name].editing
}

function cancelEzdfsEdit(item) {
  ezdfsDrafts[item.module_name] = {
    editing: false,
    values: {
      module_name: item.module_name,
      port: item.port,
      home_dir_path: item.home_dir_path,
      host_name: item.host_name,
      login_user: item.login_user,
    },
  }
}

async function updateEzdfs(item) {
  const draft = ezdfsDraft(item)
  await apiPut(`/api/admin/ezdfs/configs/${item.module_name}`, {
    ...draft.values,
    port: Number(draft.values.port),
  })
  draft.editing = false
  await loadAll()
  uiStore.setNotice(`${draft.values.module_name} ezDFS 설정이 반영되었습니다.`)
}

async function deleteEzdfs(moduleName) {
  if (!(await uiStore.confirmAction('정말 삭제하시겠습니까?', { title: 'ezDFS 설정 삭제' }))) return
  await apiDelete(`/api/admin/ezdfs/configs/${moduleName}`)
  await loadAll()
}
</script>

<template>
  <section class="page-grid">
    <article class="admin-tabs-shell panel-span-2">
      <div class="admin-tab-strip">
        <button class="admin-tab-button" :data-active="activeTab === 'users'" @click="activeTab = 'users'">
          User Management
        </button>
        <button class="admin-tab-button" :data-active="activeTab === 'hosts'" @click="activeTab = 'hosts'">
          Host Settings
        </button>
        <button class="admin-tab-button" :data-active="activeTab === 'rtd'" @click="activeTab = 'rtd'">
          RTD Settings
        </button>
        <button class="admin-tab-button" :data-active="activeTab === 'ezdfs'" @click="activeTab = 'ezdfs'">
          ezDFS Settings
        </button>
      </div>

      <div class="admin-tab-panel admin-console-panel">
        <div v-if="activeTab === 'users'" class="table-wrap console-grid-table">
          <div class="panel-head user-filter-bar">
            <label class="compact-filter">
              <span class="compact-filter-label">Module</span>
              <div class="compact-filter-control">
                <select v-model="selectedUserModule">
                  <option v-for="moduleName in userModules" :key="moduleName" :value="moduleName">
                    {{ moduleName }}
                  </option>
                </select>
              </div>
            </label>
          </div>

          <table class="data-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Name</th>
                <th>Module</th>
                <th>Approved</th>
                <th>Admin</th>
                <th>Apply</th>
                <th>Delete</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.user_id">
                <td>{{ user.user_id }}</td>
                <td>{{ user.user_name }}</td>
                <td>
                  <div class="inline-edit-cell">
                    <template v-if="userDraft(user)?.editing.module_name">
                      <input v-model="userDraft(user).values.module_name" class="inline-input" />
                    </template>
                    <template v-else>
                      <span>{{ userDraft(user)?.values.module_name }}</span>
                    </template>
                    <button class="edit-icon-button" type="button" @click="toggleUserEdit(user.user_id, 'module_name')">
                      Edit
                    </button>
                  </div>
                </td>
                <td>
                  <div class="inline-edit-cell">
                    <template v-if="userDraft(user)?.editing.is_approved">
                      <select v-model="userDraft(user).values.is_approved" class="inline-select">
                        <option :value="true">Y</option>
                        <option :value="false">N</option>
                      </select>
                    </template>
                    <template v-else>
                      <span>{{ userDraft(user)?.values.is_approved ? 'Y' : 'N' }}</span>
                    </template>
                    <button class="edit-icon-button" type="button" @click="toggleUserEdit(user.user_id, 'is_approved')">
                      Edit
                    </button>
                  </div>
                </td>
                <td>
                  <div class="inline-edit-cell">
                    <template v-if="userDraft(user)?.editing.is_admin">
                      <select v-model="userDraft(user).values.is_admin" class="inline-select">
                        <option :value="true">Y</option>
                        <option :value="false">N</option>
                      </select>
                    </template>
                    <template v-else>
                      <span>{{ userDraft(user)?.values.is_admin ? 'Y' : 'N' }}</span>
                    </template>
                    <button class="edit-icon-button" type="button" @click="toggleUserEdit(user.user_id, 'is_admin')">
                      Edit
                    </button>
                  </div>
                </td>
                <td>
                  <button class="button button-secondary" :disabled="!userChanged(user)" @click="applyUser(user)">
                    반영
                  </button>
                </td>
                <td>
                  <button class="button button-danger" @click="removeUser(user.user_id)">삭제</button>
                </td>
              </tr>
              <tr v-if="!filteredUsers.length">
                <td colspan="7" class="muted">등록된 사용자가 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else-if="activeTab === 'hosts'" class="admin-grid admin-console-grid">
          <form class="panel-subcard admin-form-panel" @submit.prevent="createHost">
            <h3>Host 추가</h3>
            <label class="field"><span>Name</span><input v-model="hostForm.name" /></label>
            <label class="field"><span>IP</span><input v-model="hostForm.ip" /></label>
            <button class="button button-primary" type="submit">등록</button>
          </form>
          <div class="table-wrap console-grid-table">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="expand-col"></th>
                  <th class="sortable-header" @click="toggleHostSort('name')">
                    <div class="sortable-header-inner">
                      <span>Name</span>
                      <span class="sort-icon" v-bind="sortState(hostSortKey, hostSortOrder, 'name')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleHostSort('ip')">
                    <div class="sortable-header-inner">
                      <span>IP</span>
                      <span class="sort-icon" v-bind="sortState(hostSortKey, hostSortOrder, 'ip')"></span>
                    </div>
                  </th>
                  <th>Credentials</th>
                  <th>SSH Limit</th>
                  <th class="sortable-header" @click="toggleHostSort('modifier')">
                    <div class="sortable-header-inner">
                      <span>Modifier</span>
                      <span class="sort-icon" v-bind="sortState(hostSortKey, hostSortOrder, 'modifier')"></span>
                    </div>
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="host in sortedHosts" :key="host.name">
                  <tr :class="{ 'editing-row': isHostEditing(host) }">
                    <td class="expand-col">
                      <button
                        class="expand-toggle-button"
                        type="button"
                        :aria-expanded="isHostExpanded(host.name)"
                        @click="toggleHostExpand(host.name)"
                      >
                        {{ isHostExpanded(host.name) ? '▼' : '▶' }}
                      </button>
                    </td>
                    <td>
                      <input v-if="hostDraft(host)?.editing" v-model="hostDraft(host).values.name" class="table-edit-input" />
                      <span v-else class="ellipsis-cell" :title="host.name">{{ host.name }}</span>
                    </td>
                    <td>
                      <input v-if="hostDraft(host)?.editing" v-model="hostDraft(host).values.ip" class="table-edit-input" />
                      <span v-else class="ellipsis-cell" :title="host.ip">{{ host.ip }}</span>
                    </td>
                    <td>
                      <span class="credential-count-badge">
                        {{ credentialsFor(host.name).length }} user{{ credentialsFor(host.name).length === 1 ? '' : 's' }}
                      </span>
                    </td>
                    <td>
                      <div class="inline-edit-cell">
                        <span
                          class="ellipsis-cell"
                          :title="hostSshLimitInfo(host.name)?.source === 'default'
                            ? 'remote 감지 실패로 기본값 10 사용'
                            : hostSshLimitInfo(host.name)?.source === 'remote'
                              ? 'remote sshd 설정 기준 감지값'
                              : '아직 감지되지 않음'"
                        >
                          {{ hostSshLimitLabel(host.name) }}
                        </span>
                        <button
                          class="edit-icon-button"
                          type="button"
                          :disabled="hostSshProbeLoading[host.name]"
                          @click="probeHostSshLimit(host.name)"
                        >
                          {{ hostSshProbeLoading[host.name] ? '...' : '감지' }}
                        </button>
                      </div>
                    </td>
                    <td class="modifier-cell">
                      <span class="modifier-text ellipsis-cell" :title="host.modifier">{{ host.modifier }}</span>
                    </td>
                    <td class="actions-cell">
                      <div class="row-action-group">
                        <button
                          v-if="hostDraft(host)?.editing"
                          class="button button-secondary"
                          :disabled="!hostChanged(host)"
                          @click="updateHost(host)"
                        >
                          반영
                        </button>
                        <button
                          v-else
                          class="button button-ghost"
                          @click="toggleHostEdit(host)"
                        >
                          수정
                        </button>
                        <button
                          v-if="hostDraft(host)?.editing"
                          class="button button-ghost"
                          @click="cancelHostEdit(host)"
                        >
                          취소
                        </button>
                        <button class="button button-danger" @click="deleteHost(host.name)">삭제</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="isHostExpanded(host.name)" class="credential-subrow">
                    <td></td>
                    <td colspan="6">
                      <div class="credential-sub-panel">
                        <table class="credential-sub-table">
                          <thead>
                            <tr>
                              <th>User</th>
                              <th>Password</th>
                              <th>Modifier</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="cred in credentialsFor(host.name)" :key="cred.login_user">
                              <td>
                                <input
                                  v-if="isCredentialEditing(host.name, cred.login_user)"
                                  v-model="credentialDraft(host.name, cred.login_user).values.login_user"
                                  class="table-edit-input"
                                />
                                <span v-else>{{ cred.login_user }}</span>
                              </td>
                              <td>
                                <input
                                  v-if="isCredentialEditing(host.name, cred.login_user)"
                                  v-model="credentialDraft(host.name, cred.login_user).values.login_password"
                                  type="password"
                                  placeholder="(변경 시 입력)"
                                  class="table-edit-input"
                                />
                                <span v-else>******</span>
                              </td>
                              <td class="modifier-cell">
                                <span class="modifier-text ellipsis-cell" :title="cred.modifier">{{ cred.modifier }}</span>
                              </td>
                              <td class="actions-cell">
                                <div class="row-action-group">
                                  <button
                                    v-if="isCredentialEditing(host.name, cred.login_user)"
                                    class="button button-secondary"
                                    @click="updateCredential(host.name, cred.login_user)"
                                  >
                                    반영
                                  </button>
                                  <button
                                    v-else
                                    class="button button-ghost"
                                    @click="toggleCredentialEdit(host.name, cred.login_user)"
                                  >
                                    수정
                                  </button>
                                  <button
                                    v-if="isCredentialEditing(host.name, cred.login_user)"
                                    class="button button-ghost"
                                    @click="cancelCredentialEdit(host.name, cred.login_user)"
                                  >
                                    취소
                                  </button>
                                  <button
                                    class="button button-danger"
                                    @click="deleteCredential(host.name, cred.login_user)"
                                  >
                                    삭제
                                  </button>
                                </div>
                              </td>
                            </tr>
                            <tr v-if="!credentialsFor(host.name).length">
                              <td colspan="4" class="muted">등록된 credential이 없습니다.</td>
                            </tr>
                            <tr v-if="credentialForm(host.name).visible" class="credential-add-row">
                              <td>
                                <input
                                  v-model="credentialForm(host.name).login_user"
                                  class="table-edit-input"
                                  placeholder="login user"
                                />
                              </td>
                              <td>
                                <input
                                  v-model="credentialForm(host.name).login_password"
                                  type="password"
                                  class="table-edit-input"
                                  placeholder="password"
                                />
                              </td>
                              <td></td>
                              <td class="actions-cell">
                                <div class="row-action-group">
                                  <button class="button button-secondary" @click="addCredential(host.name)">저장</button>
                                  <button class="button button-ghost" @click="cancelCredentialForm(host.name)">취소</button>
                                </div>
                              </td>
                            </tr>
                            <tr v-else class="credential-add-row">
                              <td colspan="4">
                                <button class="button button-ghost credential-add-trigger" @click="showCredentialForm(host.name)">
                                  + Add Credential
                                </button>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="!sortedHosts.length">
                  <td colspan="7" class="muted">표시할 Host 설정이 없습니다.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else-if="activeTab === 'rtd'" class="admin-grid admin-console-grid">
          <form class="panel-subcard admin-form-panel" @submit.prevent="createRtdConfig">
            <h3>RTD Config 추가</h3>
            <label class="field"><span>Line Name</span><input v-model="rtdForm.line_name" /></label>
            <label class="field"><span>Line ID</span><input v-model="rtdForm.line_id" /></label>
            <label class="field"><span>Business Unit</span><input v-model="rtdForm.business_unit" /></label>
            <label class="field"><span>Home Path</span><input v-model="rtdForm.home_dir_path" /></label>
            <label class="field">
              <span>Host</span>
              <select v-model="rtdForm.host_name" @change="onRtdFormHostChange">
                <option disabled value="">선택</option>
                <option v-for="host in hostOptions" :key="host" :value="host">{{ host }}</option>
              </select>
            </label>
            <label class="field">
              <span>Login User</span>
              <select v-model="rtdForm.login_user" :disabled="!rtdForm.host_name">
                <option disabled value="">선택</option>
                <option v-for="user in rtdLoginUserOptions" :key="user" :value="user">{{ user }}</option>
              </select>
            </label>
            <button class="button button-primary" type="submit">등록</button>
          </form>
          <div class="table-wrap console-grid-table">
            <div class="panel-head user-filter-bar">
              <label class="compact-filter">
                <span class="compact-filter-label">사업부</span>
                <div class="compact-filter-control">
                  <select v-model="selectedRtdBusinessUnit">
                    <option v-for="businessUnit in rtdBusinessUnits" :key="businessUnit" :value="businessUnit">
                      {{ businessUnit }}
                    </option>
                  </select>
                </div>
              </label>
            </div>
            <table class="data-table">
              <thead>
                <tr>
                  <th class="sortable-header" @click="toggleRtdSort('line_name')">
                    <div class="sortable-header-inner">
                      <span>Line</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'line_name')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('line_id')">
                    <div class="sortable-header-inner">
                      <span>ID</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'line_id')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('business_unit')">
                    <div class="sortable-header-inner">
                      <span>사업부</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'business_unit')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('home_dir_path')">
                    <div class="sortable-header-inner">
                      <span>Home Path</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'home_dir_path')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('host_name')">
                    <div class="sortable-header-inner">
                      <span>Host</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'host_name')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('login_user')">
                    <div class="sortable-header-inner">
                      <span>Login User</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'login_user')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleRtdSort('modifier')">
                    <div class="sortable-header-inner">
                      <span>Modifier</span>
                      <span class="sort-icon" v-bind="sortState(rtdSortKey, rtdSortOrder, 'modifier')"></span>
                    </div>
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredRtdConfigs" :key="item.line_name" :class="{ 'editing-row': isRtdEditing(item) }">
                  <td>
                    <input v-if="rtdDraft(item)?.editing" v-model="rtdDraft(item).values.line_name" class="table-edit-input" />
                    <span v-else>{{ item.line_name }}</span>
                  </td>
                  <td>
                    <input v-if="rtdDraft(item)?.editing" v-model="rtdDraft(item).values.line_id" class="table-edit-input" />
                    <span v-else>{{ item.line_id }}</span>
                  </td>
                  <td>
                    <input
                      v-if="rtdDraft(item)?.editing"
                      v-model="rtdDraft(item).values.business_unit"
                      class="table-edit-input"
                    />
                    <span v-else>{{ item.business_unit }}</span>
                  </td>
                  <td>
                    <input
                      v-if="rtdDraft(item)?.editing"
                      v-model="rtdDraft(item).values.home_dir_path"
                      class="table-edit-input path-edit-input"
                    />
                    <span v-else class="path-cell" :title="item.home_dir_path">{{ item.home_dir_path }}</span>
                  </td>
                  <td>
                    <select
                      v-if="rtdDraft(item)?.editing"
                      v-model="rtdDraft(item).values.host_name"
                      class="table-edit-select"
                      @change="onRtdDraftHostChange(item)"
                    >
                      <option v-for="host in hostOptions" :key="host" :value="host">{{ host }}</option>
                    </select>
                    <span v-else>{{ item.host_name }}</span>
                  </td>
                  <td>
                    <select
                      v-if="rtdDraft(item)?.editing"
                      v-model="rtdDraft(item).values.login_user"
                      class="table-edit-select"
                      :disabled="!rtdDraft(item).values.host_name"
                    >
                      <option disabled value="">선택</option>
                      <option
                        v-for="user in loginUserOptionsFor(rtdDraft(item).values.host_name)"
                        :key="user"
                        :value="user"
                      >
                        {{ user }}
                      </option>
                    </select>
                    <span v-else>{{ item.login_user }}</span>
                  </td>
                  <td class="modifier-cell">
                    <span class="modifier-text ellipsis-cell" :title="item.modifier">{{ item.modifier }}</span>
                  </td>
                  <td class="actions-cell">
                    <div class="row-action-group">
                      <button
                        v-if="rtdDraft(item)?.editing"
                        class="button button-secondary"
                        :disabled="!rtdChanged(item)"
                        @click="updateRtd(item)"
                      >
                        반영
                      </button>
                      <button
                        v-else
                        class="button button-ghost"
                        @click="toggleRtdEdit(item)"
                      >
                        수정
                      </button>
                      <button
                        v-if="rtdDraft(item)?.editing"
                        class="button button-ghost"
                        @click="cancelRtdEdit(item)"
                      >
                        취소
                      </button>
                      <button class="button button-danger" @click="deleteRtd(item.line_name)">삭제</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!filteredRtdConfigs.length">
                  <td colspan="8" class="muted">표시할 RTD 설정이 없습니다.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else class="admin-grid admin-console-grid">
          <form class="panel-subcard admin-form-panel" @submit.prevent="createEzdfsConfig">
            <h3>ezDFS Config 추가</h3>
            <label class="field"><span>Module Name</span><input v-model="ezdfsForm.module_name" /></label>
            <label class="field"><span>Port</span><input v-model="ezdfsForm.port" type="number" /></label>
            <label class="field"><span>Home Path</span><input v-model="ezdfsForm.home_dir_path" /></label>
            <label class="field">
              <span>Host</span>
              <select v-model="ezdfsForm.host_name" @change="onEzdfsFormHostChange">
                <option disabled value="">선택</option>
                <option v-for="host in hostOptions" :key="host" :value="host">{{ host }}</option>
              </select>
            </label>
            <label class="field">
              <span>Login User</span>
              <select v-model="ezdfsForm.login_user" :disabled="!ezdfsForm.host_name">
                <option disabled value="">선택</option>
                <option v-for="user in ezdfsLoginUserOptions" :key="user" :value="user">{{ user }}</option>
              </select>
            </label>
            <button class="button button-primary" type="submit">등록</button>
          </form>
          <div class="table-wrap console-grid-table">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="sortable-header" @click="toggleEzdfsSort('module_name')">
                    <div class="sortable-header-inner">
                      <span>Module</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'module_name')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleEzdfsSort('port')">
                    <div class="sortable-header-inner">
                      <span>Port</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'port')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleEzdfsSort('home_dir_path')">
                    <div class="sortable-header-inner">
                      <span>Home Path</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'home_dir_path')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleEzdfsSort('host_name')">
                    <div class="sortable-header-inner">
                      <span>Host</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'host_name')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleEzdfsSort('login_user')">
                    <div class="sortable-header-inner">
                      <span>Login User</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'login_user')"></span>
                    </div>
                  </th>
                  <th class="sortable-header" @click="toggleEzdfsSort('modifier')">
                    <div class="sortable-header-inner">
                      <span>Modifier</span>
                      <span class="sort-icon" v-bind="sortState(ezdfsSortKey, ezdfsSortOrder, 'modifier')"></span>
                    </div>
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in sortedEzdfsConfigs"
                  :key="item.module_name"
                  :class="{ 'editing-row': isEzdfsEditing(item) }"
                >
                  <td>
                    <input
                      v-if="ezdfsDraft(item)?.editing"
                      v-model="ezdfsDraft(item).values.module_name"
                      class="table-edit-input"
                    />
                    <span v-else class="ellipsis-cell" :title="item.module_name">{{ item.module_name }}</span>
                  </td>
                  <td>
                    <input
                      v-if="ezdfsDraft(item)?.editing"
                      v-model="ezdfsDraft(item).values.port"
                      type="number"
                      class="table-edit-input"
                    />
                    <span v-else>{{ item.port }}</span>
                  </td>
                  <td>
                    <input
                      v-if="ezdfsDraft(item)?.editing"
                      v-model="ezdfsDraft(item).values.home_dir_path"
                      class="table-edit-input path-edit-input"
                    />
                    <span v-else class="path-cell" :title="item.home_dir_path">{{ item.home_dir_path }}</span>
                  </td>
                  <td>
                    <select
                      v-if="ezdfsDraft(item)?.editing"
                      v-model="ezdfsDraft(item).values.host_name"
                      class="table-edit-select"
                      @change="onEzdfsDraftHostChange(item)"
                    >
                      <option v-for="host in hostOptions" :key="host" :value="host">{{ host }}</option>
                    </select>
                    <span v-else class="ellipsis-cell" :title="item.host_name">{{ item.host_name }}</span>
                  </td>
                  <td>
                    <select
                      v-if="ezdfsDraft(item)?.editing"
                      v-model="ezdfsDraft(item).values.login_user"
                      class="table-edit-select"
                      :disabled="!ezdfsDraft(item).values.host_name"
                    >
                      <option disabled value="">선택</option>
                      <option
                        v-for="user in loginUserOptionsFor(ezdfsDraft(item).values.host_name)"
                        :key="user"
                        :value="user"
                      >
                        {{ user }}
                      </option>
                    </select>
                    <span v-else>{{ item.login_user }}</span>
                  </td>
                  <td class="modifier-cell">
                    <span class="modifier-text ellipsis-cell" :title="item.modifier">{{ item.modifier }}</span>
                  </td>
                  <td class="actions-cell">
                    <div class="row-action-group">
                      <button
                        v-if="ezdfsDraft(item)?.editing"
                        class="button button-secondary"
                        :disabled="!ezdfsChanged(item)"
                        @click="updateEzdfs(item)"
                      >
                        반영
                      </button>
                      <button
                        v-else
                        class="button button-ghost"
                        @click="toggleEzdfsEdit(item)"
                      >
                        수정
                      </button>
                      <button
                        v-if="ezdfsDraft(item)?.editing"
                        class="button button-ghost"
                        @click="cancelEzdfsEdit(item)"
                      >
                        취소
                      </button>
                      <button class="button button-danger" @click="deleteEzdfs(item.module_name)">삭제</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!sortedEzdfsConfigs.length">
                  <td colspan="7" class="muted">표시할 ezDFS 설정이 없습니다.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
