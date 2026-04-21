<script setup>
import { computed, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAdminStore } from "../../stores/admin";
import { useUiStore } from "../../stores/ui";
import { sortItems, useSort } from "./sortHelpers";

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { users } = storeToRefs(adminStore);

const {
  sortKey,
  sortOrder,
  toggle: toggleUserSort,
  stateOf: userSortState,
} = useSort("user_id");

const selectedUserModule = ref("ALL");
const userDrafts = reactive({});

const userModules = computed(() => {
  const modules = [
    ...new Set(users.value.map((user) => user.module_name).filter(Boolean)),
  ];
  return ["ALL", ...modules.sort((a, b) => a.localeCompare(b))];
});

const filteredUsers = computed(() => {
  const filtered =
    selectedUserModule.value === "ALL"
      ? [...users.value]
      : users.value.filter(
          (user) => user.module_name === selectedUserModule.value,
        );
  return sortItems(filtered, sortKey.value, sortOrder.value);
});

function syncUserDrafts() {
  for (const user of users.value) {
    userDrafts[user.user_id] = {
      editing: userDrafts[user.user_id]?.editing ?? false,
      values: {
        module_name: user.module_name,
        is_approved: user.is_approved,
        is_admin: user.is_admin,
      },
    };
  }
}

watch(users, syncUserDrafts, { immediate: true });

function userDraft(user) {
  return userDrafts[user.user_id];
}

function isUserEditing(user) {
  return Boolean(userDraft(user)?.editing);
}

function userChanged(user) {
  const draft = userDraft(user);
  if (!draft) return false;
  return (
    draft.values.module_name !== user.module_name ||
    draft.values.is_approved !== user.is_approved ||
    draft.values.is_admin !== user.is_admin
  );
}

function toggleUserEdit(user) {
  userDrafts[user.user_id].editing = !userDrafts[user.user_id].editing;
}

function cancelUserEdit(user) {
  userDrafts[user.user_id] = {
    editing: false,
    values: {
      module_name: user.module_name,
      is_approved: user.is_approved,
      is_admin: user.is_admin,
    },
  };
}

async function applyUser(user) {
  const draft = userDraft(user);
  await adminStore.updateUser(user.user_id, {
    module_name: draft.values.module_name,
    is_approved: draft.values.is_approved,
    is_admin: draft.values.is_admin,
  });
  draft.editing = false;
  uiStore.setNotice(`${user.user_id} 정보가 반영되었습니다.`);
}

async function removeUser(userId) {
  if (
    !(await uiStore.confirmAction("이 사용자를 삭제하시겠습니까?", {
      title: "사용자 삭제",
    }))
  )
    return;
  await adminStore.deleteUser(userId);
}
</script>

<template>
  <div class="admin-table-stack">
    <div class="user-filter-bar">
      <label class="compact-filter">
        <span class="compact-filter-label">Module</span>
        <div class="compact-filter-control">
          <select v-model="selectedUserModule">
            <option
              v-for="moduleName in userModules"
              :key="moduleName"
              :value="moduleName"
            >
              {{ moduleName }}
            </option>
          </select>
        </div>
      </label>
    </div>

    <div class="table-wrap console-grid-table">
      <table class="data-table">
      <thead>
        <tr>
          <th class="sortable-header" @click="toggleUserSort('user_id')">
            <div class="sortable-header-inner">
              <span>User ID</span>
              <span class="sort-icon" v-bind="userSortState('user_id')"></span>
            </div>
          </th>
          <th class="sortable-header" @click="toggleUserSort('user_name')">
            <div class="sortable-header-inner">
              <span>Name</span>
              <span class="sort-icon" v-bind="userSortState('user_name')"></span>
            </div>
          </th>
          <th class="sortable-header" @click="toggleUserSort('module_name')">
            <div class="sortable-header-inner">
              <span>Module</span>
              <span
                class="sort-icon"
                v-bind="userSortState('module_name')"
              ></span>
            </div>
          </th>
          <th class="sortable-header" @click="toggleUserSort('is_approved')">
            <div class="sortable-header-inner">
              <span>Approved</span>
              <span
                class="sort-icon"
                v-bind="userSortState('is_approved')"
              ></span>
            </div>
          </th>
          <th class="sortable-header" @click="toggleUserSort('is_admin')">
            <div class="sortable-header-inner">
              <span>Admin</span>
              <span class="sort-icon" v-bind="userSortState('is_admin')"></span>
            </div>
          </th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="user in filteredUsers"
          :key="user.user_id"
          :class="{ 'editing-row': isUserEditing(user) }"
        >
          <td>
            <span class="ellipsis-cell" :title="user.user_id">{{
              user.user_id
            }}</span>
          </td>
          <td>
            <span class="ellipsis-cell" :title="user.user_name">{{
              user.user_name
            }}</span>
          </td>
          <td>
            <input
              v-if="userDraft(user)?.editing"
              v-model="userDraft(user).values.module_name"
              class="table-edit-input"
            />
            <span v-else class="ellipsis-cell" :title="user.module_name">{{
              user.module_name
            }}</span>
          </td>
          <td>
            <select
              v-if="userDraft(user)?.editing"
              v-model="userDraft(user).values.is_approved"
              class="table-edit-select"
            >
              <option :value="true">Y</option>
              <option :value="false">N</option>
            </select>
            <span v-else>{{ user.is_approved ? "Y" : "N" }}</span>
          </td>
          <td>
            <select
              v-if="userDraft(user)?.editing"
              v-model="userDraft(user).values.is_admin"
              class="table-edit-select"
            >
              <option :value="true">Y</option>
              <option :value="false">N</option>
            </select>
            <span v-else>{{ user.is_admin ? "Y" : "N" }}</span>
          </td>
          <td class="actions-cell">
            <div class="row-action-group">
              <button
                v-if="userDraft(user)?.editing"
                class="button button-secondary"
                :disabled="!userChanged(user)"
                @click="applyUser(user)"
              >
                반영
              </button>
              <button
                v-else
                class="button button-ghost"
                @click="toggleUserEdit(user)"
              >
                수정
              </button>
              <button
                v-if="userDraft(user)?.editing"
                class="button button-ghost"
                @click="cancelUserEdit(user)"
              >
                취소
              </button>
              <button
                class="button button-danger"
                @click="removeUser(user.user_id)"
              >
                삭제
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="!filteredUsers.length">
          <td colspan="6" class="muted">등록된 사용자가 없습니다.</td>
        </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
