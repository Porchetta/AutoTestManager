<script setup>
import { onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import { useAuthStore } from "../../stores/auth";
import { useRtdStore } from "../../stores/rtd";
import { useUiStore } from "../../stores/ui";

const emit = defineEmits(["show-result"]);

const authStore = useAuthStore();
const rtdStore = useRtdStore();
const uiStore = useUiStore();
const { selectedRuleTargets, svnUpload } = storeToRefs(rtdStore);

const svnUploading = ref(false);
const svnForm = ref({
  adUser: "",
  adPassword: "",
  svnNo: "",
});

onMounted(() => {
  svnForm.value = {
    adUser: svnUpload.value?.ad_user || authStore.user?.user_id || "",
    adPassword: "",
    svnNo: svnUpload.value?.svn_no || "",
  };
});

async function submitSvnUpload() {
  if (!svnForm.value.adUser || !svnForm.value.adPassword) {
    uiStore.setError("AD 계정과 비밀번호를 모두 입력해주세요.");
    return;
  }

  svnUploading.value = true;
  try {
    const result = await rtdStore.uploadSvn(
      svnForm.value.adUser,
      svnForm.value.adPassword,
    );
    svnForm.value.svnNo = result?.svn_no || "";
    svnForm.value.adPassword = "";
    uiStore.setNotice("SVN Upload가 완료되었습니다.");
  } finally {
    svnUploading.value = false;
  }
}
</script>

<template>
  <div class="operation-console-side svn-upload-inline-panel">
    <div class="operation-process-head">
      <p class="eyebrow">SVN Upload</p>
    </div>
    <form class="svn-upload-inline-row" @submit.prevent="submitSvnUpload">
      <label class="svn-upload-inline-field">
        <span class="svn-upload-inline-label">AD 계정</span>
        <input
          v-model="svnForm.adUser"
          type="text"
          autocomplete="username"
        />
      </label>
      <label class="svn-upload-inline-field">
        <span class="svn-upload-inline-label">PW</span>
        <input
          v-model="svnForm.adPassword"
          type="password"
          autocomplete="current-password"
        />
      </label>
      <div class="svn-upload-inline-action">
        <button
          class="button button-primary"
          type="submit"
          :disabled="svnUploading || !selectedRuleTargets.length"
        >
          {{ svnUploading ? "Uploading..." : "Upload" }}
        </button>
      </div>
      <div
        class="svn-upload-inline-divider"
        aria-hidden="true"
      ></div>
      <label class="svn-upload-inline-field svn-upload-inline-result">
        <span class="svn-upload-inline-label">SVN No.</span>
        <input :value="svnForm.svnNo" type="text" readonly />
      </label>
      <div class="svn-upload-inline-action">
        <button
          class="button button-ghost"
          type="button"
          :disabled="!svnForm.svnNo"
          @click="emit('show-result')"
        >
          Result
        </button>
      </div>
    </form>
  </div>
</template>
