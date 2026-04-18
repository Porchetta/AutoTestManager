<script setup>
import { computed, reactive, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAdminStore } from "../../stores/admin";
import { useUiStore } from "../../stores/ui";
import { sortItems, useSort } from "./sortHelpers";

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { hosts, hostSshProbeLoading } = storeToRefs(adminStore);

const { sortKey, sortOrder, toggle: toggleHostSort, stateOf: hostSortState } = useSort("name");

const hostForm = reactive({ name: "", ip: "" });
const hostDrafts = reactive({});
const expandedHosts = reactive(new Set());
const credentialDrafts = reactive({});
const credentialForms = reactive({});

const sortedHosts = computed(() =>
  sortItems(hosts.value, sortKey.value, sortOrder.value),
);

function syncHostDrafts() {
  for (const host of hosts.value) {
    hostDrafts[host.name] = {
      editing: hostDrafts[host.name]?.editing ?? false,
      values: {
        name: host.name,
        ip: host.ip,
      },
    };
    syncCredentialDrafts(host);
    if (!credentialForms[host.name]) {
      credentialForms[host.name] = {
        login_user: "",
        login_password: "",
        visible: false,
      };
    }
  }
}

function syncCredentialDrafts(host) {
  const map = credentialDrafts[host.name] || {};
  const nextKeys = new Set();
  for (const cred of host.credentials || []) {
    nextKeys.add(cred.login_user);
    map[cred.login_user] = {
      editing: map[cred.login_user]?.editing ?? false,
      values: {
        login_user: cred.login_user,
        login_password: "",
      },
    };
  }
  for (const key of Object.keys(map)) {
    if (!nextKeys.has(key)) delete map[key];
  }
  credentialDrafts[host.name] = map;
}

watch(hosts, syncHostDrafts, { immediate: true });

function hostDraft(host) {
  return hostDrafts[host.name];
}
function isHostEditing(host) {
  return Boolean(hostDraft(host)?.editing);
}
function hostChanged(host) {
  const draft = hostDraft(host);
  if (!draft) return false;
  return draft.values.name !== host.name || draft.values.ip !== host.ip;
}

async function createHost() {
  await adminStore.createHost(hostForm);
  Object.assign(hostForm, { name: "", ip: "" });
}

function toggleHostEdit(host) {
  hostDrafts[host.name].editing = !hostDrafts[host.name].editing;
}

function cancelHostEdit(host) {
  hostDrafts[host.name] = {
    editing: false,
    values: { name: host.name, ip: host.ip },
  };
}

async function updateHost(host) {
  const draft = hostDraft(host);
  await adminStore.updateHost(host.name, draft.values);
  draft.editing = false;
  uiStore.setNotice(`${draft.values.name} host 정보가 반영되었습니다.`);
}

async function deleteHost(name) {
  if (
    !(await uiStore.confirmAction("이 host를 삭제하시겠습니까?", {
      title: "Host 삭제",
    }))
  )
    return;
  await adminStore.deleteHost(name);
}

async function probeHostSshLimit(hostName) {
  await adminStore.probeHostSshLimit(hostName);
  uiStore.setNotice(`${hostName} SSH Limit 감지가 완료되었습니다.`);
}

function isHostExpanded(hostName) {
  return expandedHosts.has(hostName);
}

function toggleHostExpand(hostName) {
  if (expandedHosts.has(hostName)) {
    expandedHosts.delete(hostName);
  } else {
    expandedHosts.add(hostName);
  }
}

function credentialForm(hostName) {
  if (!credentialForms[hostName]) {
    credentialForms[hostName] = {
      login_user: "",
      login_password: "",
      visible: false,
    };
  }
  return credentialForms[hostName];
}

function showCredentialForm(hostName) {
  credentialForm(hostName).visible = true;
}

function cancelCredentialForm(hostName) {
  credentialForms[hostName] = {
    login_user: "",
    login_password: "",
    visible: false,
  };
}

async function addCredential(hostName) {
  const form = credentialForm(hostName);
  if (!form.login_user.trim() || !form.login_password) {
    uiStore.setNotice("login_user와 password를 입력하세요.");
    return;
  }
  await adminStore.addCredential(hostName, {
    login_user: form.login_user.trim(),
    login_password: form.login_password,
  });
  cancelCredentialForm(hostName);
  uiStore.setNotice(`${hostName}에 credential이 추가되었습니다.`);
}

function credentialDraft(hostName, loginUser) {
  return credentialDrafts[hostName]?.[loginUser];
}

function isCredentialEditing(hostName, loginUser) {
  return Boolean(credentialDraft(hostName, loginUser)?.editing);
}

function toggleCredentialEdit(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser);
  if (!draft) return;
  draft.editing = !draft.editing;
  if (!draft.editing) {
    draft.values = { login_user: loginUser, login_password: "" };
  }
}

function cancelCredentialEdit(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser);
  if (!draft) return;
  draft.editing = false;
  draft.values = { login_user: loginUser, login_password: "" };
}

async function updateCredential(hostName, loginUser) {
  const draft = credentialDraft(hostName, loginUser);
  if (!draft) return;
  const payload = {
    login_user: draft.values.login_user.trim(),
  };
  if (draft.values.login_password) {
    payload.login_password = draft.values.login_password;
  }
  await adminStore.updateCredential(hostName, loginUser, payload);
  uiStore.setNotice(`${hostName}/${loginUser} credential이 수정되었습니다.`);
}

async function deleteCredential(hostName, loginUser) {
  if (
    !(await uiStore.confirmAction(
      `${loginUser} credential을 삭제하시겠습니까?`,
      { title: "Credential 삭제" },
    ))
  )
    return;
  await adminStore.deleteCredential(hostName, loginUser);
}
</script>

<template>
  <div class="admin-grid admin-console-grid">
    <form class="panel-subcard admin-form-panel" @submit.prevent="createHost">
      <h3>Host 추가</h3>
      <label class="field"
        ><span>Name</span><input v-model="hostForm.name"
      /></label>
      <label class="field"
        ><span>IP</span><input v-model="hostForm.ip"
      /></label>
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
                <span class="sort-icon" v-bind="hostSortState('name')"></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleHostSort('ip')">
              <div class="sortable-header-inner">
                <span>IP</span>
                <span class="sort-icon" v-bind="hostSortState('ip')"></span>
              </div>
            </th>
            <th>Credentials</th>
            <th>SSH Limit</th>
            <th class="sortable-header" @click="toggleHostSort('modifier')">
              <div class="sortable-header-inner">
                <span>Modifier</span>
                <span class="sort-icon" v-bind="hostSortState('modifier')"></span>
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
                  {{ isHostExpanded(host.name) ? "▼" : "▶" }}
                </button>
              </td>
              <td>
                <input
                  v-if="hostDraft(host)?.editing"
                  v-model="hostDraft(host).values.name"
                  class="table-edit-input"
                />
                <span
                  v-else
                  class="ellipsis-cell"
                  :title="host.name"
                  >{{ host.name }}</span
                >
              </td>
              <td>
                <input
                  v-if="hostDraft(host)?.editing"
                  v-model="hostDraft(host).values.ip"
                  class="table-edit-input"
                />
                <span v-else class="ellipsis-cell" :title="host.ip">{{
                  host.ip
                }}</span>
              </td>
              <td>
                <span class="credential-count-badge">
                  {{ adminStore.credentialsFor(host.name).length }} user{{
                    adminStore.credentialsFor(host.name).length === 1 ? "" : "s"
                  }}
                </span>
              </td>
              <td>
                <div class="inline-edit-cell">
                  <span
                    class="ellipsis-cell"
                    :title="
                      adminStore.hostSshLimitInfo(host.name)?.source === 'default'
                        ? 'remote 감지 실패로 기본값 10 사용'
                        : adminStore.hostSshLimitInfo(host.name)?.source === 'remote'
                          ? 'remote sshd 설정 기준 감지값'
                          : '아직 감지되지 않음'
                    "
                  >
                    {{ adminStore.hostSshLimitLabel(host.name) }}
                  </span>
                  <button
                    class="edit-icon-button"
                    type="button"
                    :disabled="hostSshProbeLoading[host.name]"
                    @click="probeHostSshLimit(host.name)"
                  >
                    {{ hostSshProbeLoading[host.name] ? "..." : "감지" }}
                  </button>
                </div>
              </td>
              <td class="modifier-cell">
                <span class="modifier-text ellipsis-cell" :title="host.modifier">{{
                  host.modifier
                }}</span>
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
                  <button class="button button-danger" @click="deleteHost(host.name)">
                    삭제
                  </button>
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
                      <tr
                        v-for="cred in adminStore.credentialsFor(host.name)"
                        :key="cred.login_user"
                      >
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
                          <span class="modifier-text ellipsis-cell" :title="cred.modifier">{{
                            cred.modifier
                          }}</span>
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
                      <tr v-if="!adminStore.credentialsFor(host.name).length">
                        <td colspan="4" class="muted">등록된 credential이 없습니다.</td>
                      </tr>
                      <tr
                        v-if="credentialForm(host.name).visible"
                        class="credential-add-row"
                      >
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
                            <button
                              class="button button-secondary"
                              @click="addCredential(host.name)"
                            >
                              저장
                            </button>
                            <button
                              class="button button-ghost"
                              @click="cancelCredentialForm(host.name)"
                            >
                              취소
                            </button>
                          </div>
                        </td>
                      </tr>
                      <tr v-else class="credential-add-row">
                        <td colspan="4">
                          <button
                            class="button button-ghost credential-add-trigger"
                            @click="showCredentialForm(host.name)"
                          >
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
</template>
