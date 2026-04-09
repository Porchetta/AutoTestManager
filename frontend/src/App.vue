<script setup>
import { storeToRefs } from 'pinia'
import { useUiStore } from './stores/ui'

const uiStore = useUiStore()
const { globalError, globalNotice, confirmDialogState } = storeToRefs(uiStore)
</script>

<template>
  <div class="app-shell">
    <transition name="fade">
      <div v-if="globalNotice" class="toast toast-notice" @click="uiStore.clearNotice()">
        {{ globalNotice }}
      </div>
    </transition>

    <transition name="fade">
      <div v-if="globalError" class="toast toast-error" @click="uiStore.clearError()">
        {{ globalError }}
      </div>
    </transition>

    <transition name="fade">
      <div v-if="confirmDialogState.open" class="modal-overlay" @click.self="uiStore.confirmDialogCancel()">
        <div class="confirm-modal">
          <p class="eyebrow">Action Check</p>
          <h3>{{ confirmDialogState.title }}</h3>
          <p class="confirm-copy">{{ confirmDialogState.message }}</p>
          <div class="confirm-actions">
            <button class="button button-ghost" @click="uiStore.confirmDialogCancel()">
              {{ confirmDialogState.cancelText }}
            </button>
            <button class="button button-danger" @click="uiStore.confirmDialogOk()">
              {{ confirmDialogState.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <RouterView />
  </div>
</template>
