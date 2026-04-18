<script setup>
import { onMounted, ref } from "vue";
import { useAdminStore } from "../stores/admin";
import UsersTab from "../components/admin/UsersTab.vue";
import HostsTab from "../components/admin/HostsTab.vue";
import RtdConfigsTab from "../components/admin/RtdConfigsTab.vue";
import EzdfsConfigsTab from "../components/admin/EzdfsConfigsTab.vue";

const adminStore = useAdminStore();
const activeTab = ref("users");

onMounted(async () => {
  await adminStore.loadAll();
});
</script>

<template>
  <section class="page-grid">
    <article class="admin-tabs-shell panel-span-2">
      <div class="admin-tab-strip">
        <button
          class="admin-tab-button"
          :data-active="activeTab === 'users'"
          @click="activeTab = 'users'"
        >
          User Management
        </button>
        <button
          class="admin-tab-button"
          :data-active="activeTab === 'hosts'"
          @click="activeTab = 'hosts'"
        >
          Host Settings
        </button>
        <button
          class="admin-tab-button"
          :data-active="activeTab === 'rtd'"
          @click="activeTab = 'rtd'"
        >
          RTD Settings
        </button>
        <button
          class="admin-tab-button"
          :data-active="activeTab === 'ezdfs'"
          @click="activeTab = 'ezdfs'"
        >
          ezDFS Settings
        </button>
      </div>

      <div class="admin-tab-panel admin-console-panel">
        <UsersTab v-if="activeTab === 'users'" />
        <HostsTab v-else-if="activeTab === 'hosts'" />
        <RtdConfigsTab v-else-if="activeTab === 'rtd'" />
        <EzdfsConfigsTab v-else />
      </div>
    </article>
  </section>
</template>
