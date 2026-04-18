<script setup>
import { computed, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAdminStore } from "../../stores/admin";
import { useUiStore } from "../../stores/ui";

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { users } = storeToRefs(adminStore);

const selectedUserModule = ref("ALL");
const userDrafts = reactive({});

const userModules = computed(() => {
  const modules = [
    ...new Set(users.value.map((user) => user.module_name).filter(Boolean)),
  ];
  return ["ALL", ...modules.sort((a, b) => a.localeCompare(b))];
});

const filteredUsers = computed(() => {
  if (selectedUserModule.value === "ALL") {
    return users.value;
  }
  return users.value.filter(
    (user) => user.module_name === selectedUserModule.value,
  );
});

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
      };
      continue;
    }
    userDrafts[user.user_id].values.module_name = user.module_name;
    userDrafts[user.user_id].values.is_approved = user.is_approved;
    userDrafts[user.user_id].values.is_admin = user.is_admin;
  }
}

watch(users, syncUserDrafts, { immediate: true });

function userDraft(user) {
  return userDrafts[user.user_id];
}

function toggleUserEdit(userId, field) {
  userDrafts[userId].editing[field] = !userDrafts[userId].editing[field];
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

async function applyUser(user) {
  const draft = userDraft(user);
  await adminStore.updateUser(user.user_id, {
    module_name: draft.values.module_name,
    is_approved: draft.values.is_approved,
    is_admin: draft.values.is_admin,
  });
  draft.editing.module_name = false;
  draft.editing.is_approved = false;
  draft.editing.is_admin = false;
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
  <div class="table-wrap console-grid-table">
    <div class="panel-head user-filter-bar">
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
                <input
                  v-model="userDraft(user).values.module_name"
                  class="inline-input"
                />
              </template>
              <template v-else>
                <span>{{ userDraft(user)?.values.module_name }}</span>
              </template>
              <button
                class="edit-icon-button"
                type="button"
                @click="toggleUserEdit(user.user_id, 'module_name')"
              >
                Edit
              </button>
            </div>
          </td>
          <td>
            <div class="inline-edit-cell">
              <template v-if="userDraft(user)?.editing.is_approved">
                <select
                  v-model="userDraft(user).values.is_approved"
                  class="inline-select"
                >
                  <option :value="true">Y</option>
                  <option :value="false">N</option>
                </select>
              </template>
              <template v-else>
                <span>{{
                  userDraft(user)?.values.is_approved ? "Y" : "N"
                }}</span>
              </template>
              <button
                class="edit-icon-button"
                type="button"
                @click="toggleUserEdit(user.user_id, 'is_approved')"
              >
                Edit
              </button>
            </div>
          </td>
          <td>
            <div class="inline-edit-cell">
              <template v-if="userDraft(user)?.editing.is_admin">
                <select
                  v-model="userDraft(user).values.is_admin"
                  class="inline-select"
                >
                  <option :value="true">Y</option>
                  <option :value="false">N</option>
                </select>
              </template>
              <template v-else>
                <span>{{ userDraft(user)?.values.is_admin ? "Y" : "N" }}</span>
              </template>
              <button
                class="edit-icon-button"
                type="button"
                @click="toggleUserEdit(user.user_id, 'is_admin')"
              >
                Edit
              </button>
            </div>
          </td>
          <td>
            <button
              class="button button-secondary"
              :disabled="!userChanged(user)"
              @click="applyUser(user)"
            >
              반영
            </button>
          </td>
          <td>
            <button
              class="button button-danger"
              @click="removeUser(user.user_id)"
            >
              삭제
            </button>
          </td>
        </tr>
        <tr v-if="!filteredUsers.length">
          <td colspan="7" class="muted">등록된 사용자가 없습니다.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
