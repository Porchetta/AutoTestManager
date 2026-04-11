<script setup>
import { computed } from "vue";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();

const menus = computed(() => {
  const baseMenus = [
    { label: "DashBoard", path: "/" },
    { label: "RTD Test", path: "/rtd" },
    { label: "ezDFS Test", path: "/ezdfs" },
    { label: "My Page", path: "/mypage" },
  ];

  if (authStore.isAdmin) {
    baseMenus.splice(3, 0, { label: "Admin", path: "/admin" });
  }

  return baseMenus;
});

</script>

<template>
  <aside class="sidebar">
    <div class="brand-card">
      <p class="eyebrow">MSS</p>
      <h2>AutoTest Manager</h2>
    </div>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in menus"
        :key="item.path"
        :to="item.path"
        class="nav-link"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
