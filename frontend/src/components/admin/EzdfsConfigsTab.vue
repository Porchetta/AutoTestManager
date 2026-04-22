<script setup>
import { computed, reactive, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAdminStore } from "../../stores/admin";
import { useUiStore } from "../../stores/ui";
import { sortItems, useSort } from "./sortHelpers";

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { ezdfsConfigs } = storeToRefs(adminStore);

const {
  sortKey,
  sortOrder,
  toggle: toggleEzdfsSort,
  stateOf: ezdfsSortState,
} = useSort("module_name");

const ezdfsDrafts = reactive({});
const ezdfsForm = reactive({
  module_name: "",
  port: 22,
  home_dir_path: "",
  host_name: "",
  login_user: "",
});

const hostOptions = computed(() => adminStore.hostOptions);
const ezdfsLoginUserOptions = computed(() =>
  adminStore.loginUserOptionsFor(ezdfsForm.host_name),
);

const sortedEzdfsConfigs = computed(() =>
  sortItems(ezdfsConfigs.value, sortKey.value, sortOrder.value),
);

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
    };
  }
}

watch(ezdfsConfigs, syncEzdfsDrafts, { immediate: true });

function ezdfsDraft(item) {
  return ezdfsDrafts[item.module_name];
}

function isEzdfsEditing(item) {
  return Boolean(ezdfsDraft(item)?.editing);
}

function ezdfsChanged(item) {
  const draft = ezdfsDraft(item);
  if (!draft) return false;
  return (
    draft.values.module_name !== item.module_name ||
    Number(draft.values.port) !== Number(item.port) ||
    draft.values.home_dir_path !== item.home_dir_path ||
    draft.values.host_name !== item.host_name ||
    draft.values.login_user !== item.login_user
  );
}

function onEzdfsFormHostChange() {
  const options = adminStore.loginUserOptionsFor(ezdfsForm.host_name);
  if (!options.includes(ezdfsForm.login_user)) ezdfsForm.login_user = "";
}

function onEzdfsDraftHostChange(item) {
  const draft = ezdfsDraft(item);
  if (!draft) return;
  const options = adminStore.loginUserOptionsFor(draft.values.host_name);
  if (!options.includes(draft.values.login_user)) draft.values.login_user = "";
}

async function createEzdfsConfig() {
  await adminStore.createEzdfsConfig({
    ...ezdfsForm,
    port: Number(ezdfsForm.port),
  });
  Object.assign(ezdfsForm, {
    module_name: "",
    port: 22,
    home_dir_path: "",
    host_name: "",
    login_user: "",
  });
}

function toggleEzdfsEdit(item) {
  ezdfsDrafts[item.module_name].editing =
    !ezdfsDrafts[item.module_name].editing;
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
  };
}

async function updateEzdfs(item) {
  const draft = ezdfsDraft(item);
  await adminStore.updateEzdfsConfig(item.module_name, {
    ...draft.values,
    port: Number(draft.values.port),
  });
  draft.editing = false;
  uiStore.setNotice(
    `${draft.values.module_name} ezDFS 설정이 반영되었습니다.`,
  );
}

async function deleteEzdfs(moduleName) {
  if (
    !(await uiStore.confirmAction("정말 삭제하시겠습니까?", {
      title: "ezDFS 설정 삭제",
    }))
  )
    return;
  await adminStore.deleteEzdfsConfig(moduleName);
}

function loginUserOptionsFor(hostName) {
  return adminStore.loginUserOptionsFor(hostName);
}
</script>

<template>
  <div class="admin-grid admin-console-grid">
    <form
      class="panel-subcard admin-form-panel"
      @submit.prevent="createEzdfsConfig"
    >
      <h3>ezDFS Config 추가</h3>
      <label class="field"
        ><span>Module Name</span><input v-model="ezdfsForm.module_name"
      /></label>
      <label class="field"
        ><span>Port</span
        ><input v-model="ezdfsForm.port" type="number"
      /></label>
      <label class="field"
        ><span>Home Path</span><input v-model="ezdfsForm.home_dir_path"
      /></label>
      <label class="field">
        <span>Host</span>
        <select v-model="ezdfsForm.host_name" @change="onEzdfsFormHostChange">
          <option disabled value="">선택</option>
          <option v-for="host in hostOptions" :key="host" :value="host">
            {{ host }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>Login User</span>
        <select v-model="ezdfsForm.login_user" :disabled="!ezdfsForm.host_name">
          <option disabled value="">선택</option>
          <option
            v-for="user in ezdfsLoginUserOptions"
            :key="user"
            :value="user"
          >
            {{ user }}
          </option>
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
                <span
                  class="sort-icon"
                  v-bind="ezdfsSortState('module_name')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleEzdfsSort('port')">
              <div class="sortable-header-inner">
                <span>Port</span>
                <span class="sort-icon" v-bind="ezdfsSortState('port')"></span>
              </div>
            </th>
            <th
              class="sortable-header"
              @click="toggleEzdfsSort('home_dir_path')"
            >
              <div class="sortable-header-inner">
                <span>Home Path</span>
                <span
                  class="sort-icon"
                  v-bind="ezdfsSortState('home_dir_path')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleEzdfsSort('host_name')">
              <div class="sortable-header-inner">
                <span>Host</span>
                <span
                  class="sort-icon"
                  v-bind="ezdfsSortState('host_name')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleEzdfsSort('login_user')">
              <div class="sortable-header-inner">
                <span>Login User</span>
                <span
                  class="sort-icon"
                  v-bind="ezdfsSortState('login_user')"
                ></span>
              </div>
            </th>
            <th class="sortable-header" @click="toggleEzdfsSort('modifier')">
              <div class="sortable-header-inner">
                <span>Modifier</span>
                <span
                  class="sort-icon"
                  v-bind="ezdfsSortState('modifier')"
                ></span>
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
              <span v-else class="ellipsis-cell" :title="item.module_name">{{
                item.module_name
              }}</span>
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
              <span v-else class="path-cell" :title="item.home_dir_path">{{
                item.home_dir_path
              }}</span>
            </td>
            <td>
              <select
                v-if="ezdfsDraft(item)?.editing"
                v-model="ezdfsDraft(item).values.host_name"
                class="table-edit-select"
                @change="onEzdfsDraftHostChange(item)"
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
                v-if="ezdfsDraft(item)?.editing"
                v-model="ezdfsDraft(item).values.login_user"
                class="table-edit-select"
                :disabled="!ezdfsDraft(item).values.host_name"
              >
                <option disabled value="">선택</option>
                <option
                  v-for="user in loginUserOptionsFor(
                    ezdfsDraft(item).values.host_name,
                  )"
                  :key="user"
                  :value="user"
                >
                  {{ user }}
                </option>
              </select>
              <span v-else>{{ item.login_user }}</span>
            </td>
            <td class="modifier-cell">
              <span class="modifier-text ellipsis-cell" :title="item.modifier">{{
                item.modifier
              }}</span>
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
                <button
                  class="button button-danger"
                  @click="deleteEzdfs(item.module_name)"
                >
                  삭제
                </button>
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
</template>
