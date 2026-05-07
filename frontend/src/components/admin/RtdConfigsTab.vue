<script setup>
import { computed, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAdminStore } from "../../stores/admin";
import { useUiStore } from "../../stores/ui";
import { sortItems, useSort } from "./sortHelpers";

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { rtdConfigs } = storeToRefs(adminStore);

const {
  sortKey,
  sortOrder,
  toggle: toggleRtdSort,
  stateOf: rtdSortState,
} = useSort("line_name");

const selectedRtdBusinessUnit = ref("ALL");
const rtdDrafts = reactive({});
const rtdForm = reactive({
  line_name: "",
  line_id: "",
  business_unit: "",
  home_dir_path: "",
  host_name: "",
  login_user: "",
});

const hostOptions = computed(() => adminStore.hostOptions);
const rtdLoginUserOptions = computed(() =>
  adminStore.loginUserOptionsFor(rtdForm.host_name),
);

const rtdBusinessUnits = computed(() => {
  const items = [
    ...new Set(
      rtdConfigs.value.map((item) => item.business_unit).filter(Boolean),
    ),
  ];
  return ["ALL", ...items.sort((a, b) => a.localeCompare(b))];
});

const filteredRtdConfigs = computed(() => {
  const filtered =
    selectedRtdBusinessUnit.value === "ALL"
      ? [...rtdConfigs.value]
      : rtdConfigs.value.filter(
          (item) => item.business_unit === selectedRtdBusinessUnit.value,
        );
  return sortItems(filtered, sortKey.value, sortOrder.value);
});

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
    };
  }
}

watch(rtdConfigs, syncRtdDrafts, { immediate: true });

function rtdDraft(item) {
  return rtdDrafts[item.line_name];
}

function isRtdEditing(item) {
  return Boolean(rtdDraft(item)?.editing);
}

function rtdChanged(item) {
  const draft = rtdDraft(item);
  if (!draft) return false;
  return (
    draft.values.line_name !== item.line_name ||
    draft.values.line_id !== item.line_id ||
    draft.values.business_unit !== item.business_unit ||
    draft.values.home_dir_path !== item.home_dir_path ||
    draft.values.host_name !== item.host_name ||
    draft.values.login_user !== item.login_user
  );
}

function onRtdFormHostChange() {
  const options = adminStore.loginUserOptionsFor(rtdForm.host_name);
  if (!options.includes(rtdForm.login_user)) rtdForm.login_user = "";
}

function onRtdDraftHostChange(item) {
  const draft = rtdDraft(item);
  if (!draft) return;
  const options = adminStore.loginUserOptionsFor(draft.values.host_name);
  if (!options.includes(draft.values.login_user)) draft.values.login_user = "";
}

async function createRtdConfig() {
  await adminStore.createRtdConfig({ ...rtdForm });
  Object.assign(rtdForm, {
    line_name: "",
    line_id: "",
    business_unit: "",
    home_dir_path: "",
    host_name: "",
    login_user: "",
  });
}

function toggleRtdEdit(item) {
  rtdDrafts[item.line_name].editing = !rtdDrafts[item.line_name].editing;
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
  };
}

async function updateRtd(item) {
  const draft = rtdDraft(item);
  const newLineName = draft.values.line_name;
  await adminStore.updateRtdConfig(item.line_name, { ...draft.values });
  if (rtdDrafts[newLineName]) {
    rtdDrafts[newLineName].editing = false;
  } else if (rtdDrafts[item.line_name]) {
    rtdDrafts[item.line_name].editing = false;
  }
  uiStore.setNotice(`${newLineName} RTD 설정이 반영되었습니다.`);
}

async function deleteRtd(lineName) {
  if (
    !(await uiStore.confirmAction("정말 삭제하시겠습니까?", {
      title: "RTD 설정 삭제",
    }))
  )
    return;
  await adminStore.deleteRtdConfig(lineName);
}

function loginUserOptionsFor(hostName) {
  return adminStore.loginUserOptionsFor(hostName);
}
</script>

<template>
  <div class="admin-grid admin-console-grid">
    <form class="panel-subcard admin-form-panel" @submit.prevent="createRtdConfig">
      <h3>RTD Config 추가</h3>
      <label class="field"
        ><span>Line Name</span><input v-model="rtdForm.line_name"
      /></label>
      <label class="field"
        ><span>Line ID</span><input v-model="rtdForm.line_id"
      /></label>
      <label class="field"
        ><span>Business Unit</span><input v-model="rtdForm.business_unit"
      /></label>
      <label class="field"
        ><span>Home Path</span><input v-model="rtdForm.home_dir_path"
      /></label>
      <label class="field">
        <span>Host</span>
        <select v-model="rtdForm.host_name" @change="onRtdFormHostChange">
          <option disabled value="">선택</option>
          <option v-for="host in hostOptions" :key="host" :value="host">
            {{ host }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>Login User</span>
        <select v-model="rtdForm.login_user" :disabled="!rtdForm.host_name">
          <option disabled value="">선택</option>
          <option
            v-for="user in rtdLoginUserOptions"
            :key="user"
            :value="user"
          >
            {{ user }}
          </option>
        </select>
      </label>
      <button class="button button-primary" type="submit">등록</button>
    </form>

    <div class="admin-table-stack">
      <div class="user-filter-bar">
        <label class="compact-filter">
          <span class="compact-filter-label">사업부</span>
          <div class="compact-filter-control">
            <select v-model="selectedRtdBusinessUnit">
              <option
                v-for="businessUnit in rtdBusinessUnits"
                :key="businessUnit"
                :value="businessUnit"
              >
                {{ businessUnit }}
              </option>
            </select>
          </div>
        </label>
      </div>

      <div class="table-wrap console-grid-table">
        <table class="data-table">
        <thead>
          <tr>
            <th class="sortable-header" @click="toggleRtdSort('line_name')">
              <div class="sortable-header-inner">
                <span>Line</span>
                <span class="sort-icon" v-bind="rtdSortState('line_name')"></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('line_id')">
              <div class="sortable-header-inner">
                <span>ID</span>
                <span class="sort-icon" v-bind="rtdSortState('line_id')"></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('business_unit')">
              <div class="sortable-header-inner">
                <span>사업부</span>
                <span
                  class="sort-icon"
                  v-bind="rtdSortState('business_unit')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('home_dir_path')">
              <div class="sortable-header-inner">
                <span>Home Path</span>
                <span
                  class="sort-icon"
                  v-bind="rtdSortState('home_dir_path')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('host_name')">
              <div class="sortable-header-inner">
                <span>Host</span>
                <span
                  class="sort-icon"
                  v-bind="rtdSortState('host_name')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('login_user')">
              <div class="sortable-header-inner">
                <span>Login User</span>
                <span
                  class="sort-icon"
                  v-bind="rtdSortState('login_user')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleRtdSort('modifier')">
              <div class="sortable-header-inner">
                <span>Modifier</span>
                <span class="sort-icon" v-bind="rtdSortState('modifier')"></span>
              </div>
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in filteredRtdConfigs"
            :key="item.line_name"
            :class="{ 'editing-row': isRtdEditing(item) }"
          >
            <td>
              <input
                v-if="rtdDraft(item)?.editing"
                v-model="rtdDraft(item).values.line_name"
                class="table-edit-input"
              />
              <span v-else class="ellipsis-cell" :title="item.line_name">{{
                item.line_name
              }}</span>
            </td>
            <td>
              <input
                v-if="rtdDraft(item)?.editing"
                v-model="rtdDraft(item).values.line_id"
                class="table-edit-input"
              />
              <span v-else class="ellipsis-cell" :title="item.line_id">{{
                item.line_id
              }}</span>
            </td>
            <td>
              <input
                v-if="rtdDraft(item)?.editing"
                v-model="rtdDraft(item).values.business_unit"
                class="table-edit-input"
              />
              <span v-else class="ellipsis-cell" :title="item.business_unit">{{
                item.business_unit
              }}</span>
            </td>
            <td>
              <input
                v-if="rtdDraft(item)?.editing"
                v-model="rtdDraft(item).values.home_dir_path"
                class="table-edit-input path-edit-input"
              />
              <span v-else class="path-cell" :title="item.home_dir_path">{{
                item.home_dir_path
              }}</span>
            </td>
            <td>
              <select
                v-if="rtdDraft(item)?.editing"
                v-model="rtdDraft(item).values.host_name"
                class="table-edit-select"
                @change="onRtdDraftHostChange(item)"
              >
                <option v-for="host in hostOptions" :key="host" :value="host">
                  {{ host }}
                </option>
              </select>
              <span v-else class="ellipsis-cell" :title="item.host_name">{{
                item.host_name
              }}</span>
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
                  v-for="user in loginUserOptionsFor(
                    rtdDraft(item).values.host_name,
                  )"
                  :key="user"
                  :value="user"
                >
                  {{ user }}
                </option>
              </select>
              <span v-else class="ellipsis-cell" :title="item.login_user">{{
                item.login_user
              }}</span>
            </td>
            <td class="modifier-cell">
              <span class="modifier-text ellipsis-cell" :title="item.modifier">{{
                item.modifier
              }}</span>
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
                <button
                  class="button button-danger"
                  @click="deleteRtd(item.line_name)"
                >
                  삭제
                </button>
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
  </div>
</template>
