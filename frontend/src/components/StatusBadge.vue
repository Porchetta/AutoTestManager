<script setup>
const props = defineProps({
  status: {
    type: String,
    default: 'READY',
  },
})
</script>

<template>
  <span class="status-badge" :data-status="props.status">{{ props.status }}</span>
</template>

