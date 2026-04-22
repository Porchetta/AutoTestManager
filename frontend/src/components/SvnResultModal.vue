<script setup>
defineProps({
  visible: { type: Boolean, required: true },
  text: { type: String, default: "" },
});

const emit = defineEmits(["close"]);
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="svn-result-overlay"
      @click.self="emit('close')"
    >
      <div class="svn-result-dialog">
        <div class="svn-result-header">
          <h4>SVN Checkin Result</h4>
          <button class="button button-ghost" type="button" @click="emit('close')">✕</button>
        </div>
        <pre class="svn-result-body">{{ text }}</pre>
      </div>
    </div>
  </Teleport>
</template>
