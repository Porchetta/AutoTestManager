import { defineStore } from "pinia";
import { computed, reactive, ref } from "vue";
import { apiDelete, apiGet, apiPost, apiPut } from "../api";

export const useAdminStore = defineStore("admin", () => {
  const users = ref([]);
  const hosts = ref([]);
  const hostSshLimits = ref({});
  const hostSshProbeLoading = reactive({});
  const rtdConfigs = ref([]);
  const ezdfsConfigs = ref([]);

  const hostOptions = computed(() => hosts.value.map((item) => item.name));
  const hostCredentialMap = computed(() => {
    const map = {};
    for (const host of hosts.value) {
      map[host.name] = Array.isArray(host.credentials) ? host.credentials : [];
    }
    return map;
  });

  function credentialsFor(hostName) {
    return hostCredentialMap.value[hostName] || [];
  }

  function loginUserOptionsFor(hostName) {
    return credentialsFor(hostName).map((cred) => cred.login_user);
  }

  function hostSshLimitInfo(hostName) {
    return hostSshLimits.value[hostName] || null;
  }

  function hostSshLimitLabel(hostName) {
    const info = hostSshLimitInfo(hostName);
    if (!info) return "-";
    if (info.source === "unknown") return "-";
    return info.source === "default"
      ? `${info.parallel_limit} (default)`
      : String(info.parallel_limit);
  }

  async function loadAll() {
    users.value = (await apiGet("/api/admin/users")).items;
    hosts.value = (await apiGet("/api/admin/hosts")).items;
    hostSshLimits.value = Object.fromEntries(
      ((await apiGet("/api/admin/hosts/ssh-limits")).items || []).map((item) => [
        item.host_name,
        item,
      ]),
    );
    rtdConfigs.value = (await apiGet("/api/admin/rtd/configs")).items;
    ezdfsConfigs.value = (await apiGet("/api/admin/ezdfs/configs")).items;
  }

  async function probeHostSshLimit(hostName) {
    if (hostSshProbeLoading[hostName]) return null;
    hostSshProbeLoading[hostName] = true;
    try {
      const result = await apiPost(
        `/api/admin/hosts/${hostName}/ssh-limits/probe`,
        {},
      );
      hostSshLimits.value = {
        ...hostSshLimits.value,
        [hostName]: result.item,
      };
      return result.item;
    } finally {
      hostSshProbeLoading[hostName] = false;
    }
  }

  async function approveUser(userId) {
    await apiPut(`/api/admin/users/${userId}/approve`, {});
    await loadAll();
  }

  async function rejectUser(userId) {
    await apiPut(`/api/admin/users/${userId}/reject`, {});
    await loadAll();
  }

  async function updateUser(userId, payload) {
    await apiPut(`/api/admin/users/${userId}`, payload);
    await loadAll();
  }

  async function deleteUser(userId) {
    await apiDelete(`/api/admin/users/${userId}`);
    await loadAll();
  }

  async function createHost(payload) {
    await apiPost("/api/admin/hosts", payload);
    await loadAll();
  }

  async function updateHost(name, payload) {
    await apiPut(`/api/admin/hosts/${name}`, payload);
    await loadAll();
  }

  async function deleteHost(name) {
    await apiDelete(`/api/admin/hosts/${name}`);
    await loadAll();
  }

  async function addCredential(hostName, payload) {
    await apiPost(`/api/admin/hosts/${hostName}/credentials`, payload);
    await loadAll();
  }

  async function updateCredential(hostName, loginUser, payload) {
    await apiPut(
      `/api/admin/hosts/${hostName}/credentials/${encodeURIComponent(loginUser)}`,
      payload,
    );
    await loadAll();
  }

  async function deleteCredential(hostName, loginUser) {
    await apiDelete(
      `/api/admin/hosts/${hostName}/credentials/${encodeURIComponent(loginUser)}`,
    );
    await loadAll();
  }

  async function createRtdConfig(payload) {
    await apiPost("/api/admin/rtd/configs", payload);
    await loadAll();
  }

  async function updateRtdConfig(lineName, payload) {
    await apiPut(`/api/admin/rtd/configs/${lineName}`, payload);
    await loadAll();
  }

  async function deleteRtdConfig(lineName) {
    await apiDelete(`/api/admin/rtd/configs/${lineName}`);
    await loadAll();
  }

  async function createEzdfsConfig(payload) {
    await apiPost("/api/admin/ezdfs/configs", payload);
    await loadAll();
  }

  async function updateEzdfsConfig(moduleName, payload) {
    await apiPut(`/api/admin/ezdfs/configs/${moduleName}`, payload);
    await loadAll();
  }

  async function deleteEzdfsConfig(moduleName) {
    await apiDelete(`/api/admin/ezdfs/configs/${moduleName}`);
    await loadAll();
  }

  return {
    users,
    hosts,
    hostSshLimits,
    hostSshProbeLoading,
    rtdConfigs,
    ezdfsConfigs,
    hostOptions,
    hostCredentialMap,
    credentialsFor,
    loginUserOptionsFor,
    hostSshLimitInfo,
    hostSshLimitLabel,
    loadAll,
    probeHostSshLimit,
    approveUser,
    rejectUser,
    updateUser,
    deleteUser,
    createHost,
    updateHost,
    deleteHost,
    addCredential,
    updateCredential,
    deleteCredential,
    createRtdConfig,
    updateRtdConfig,
    deleteRtdConfig,
    createEzdfsConfig,
    updateEzdfsConfig,
    deleteEzdfsConfig,
  };
});
