<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import StatusBadge from '../components/StatusBadge.vue'
import { useEzdfsStore } from '../stores/ezdfs'
import { useUiStore } from '../stores/ui'

const ezdfsStore = useEzdfsStore()
const uiStore = useUiStore()
const { selectedModule, selectedRule, currentTask, tasks, modules, rules } = storeToRefs(ezdfsStore)

let pollId = null

onMounted(async () => {
  await ezdfsStore.loadInitialData()
  pollId = window.setInterval(() => {
    ezdfsStore.refreshTasks()
  }, 3000)
})

onBeforeUnmount(() => {
  if (pollId) window.clearInterval(pollId)
})

async function chooseModule() {
  selectedRule.value = ''
  await ezdfsStore.loadRules()
  await ezdfsStore.saveSession()
}

async function run(action) {
  if (!selectedModule.value || !selectedRule.value) {
    uiStore.setError('module과 rule을 먼저 선택해주세요.')
    return
  }
  await ezdfsStore.run(action)
  uiStore.setNotice(`${action.toUpperCase()} 요청이 등록되었습니다.`)
}
</script>

<template>
  <section class="page-grid">
    <article class="panel">
      <div class="panel-head">
        <h3>Step 1. Module 선택</h3>
      </div>
      <div class="choice-grid">
        <button
          v-for="item in modules"
          :key="item"
          class="choice-card"
          :data-selected="selectedModule === item"
          @click="selectedModule = item; chooseModule()"
        >
          {{ item }}
        </button>
      </div>
    </article>

    <article class="panel">
      <div class="panel-head">
        <h3>Step 2. Rule 선택</h3>
      </div>
      <div class="choice-grid">
        <button
          v-for="item in rules"
          :key="item"
          class="choice-card"
          :data-selected="selectedRule === item"
          @click="selectedRule = item; ezdfsStore.saveSession()"
        >
          {{ item }}
        </button>
      </div>
    </article>

    <article class="panel panel-span-2">
      <div class="panel-head">
        <h3>Step 3. Test Manager</h3>
        <div class="button-row">
          <button class="button button-accent" @click="run('test')">테스트 실행</button>
          <button class="button button-secondary" @click="run('retest')">재테스트</button>
        </div>
      </div>
      <div class="summary-band">
        <span>Module: {{ selectedModule || '-' }}</span>
        <span>Rule: {{ selectedRule || '-' }}</span>
        <span>Current Task: {{ currentTask?.task_id || '-' }}</span>
      </div>
      <div class="task-grid">
        <div v-for="task in tasks" :key="task.task_id" class="task-card">
          <div class="task-head">
            <strong>{{ task.target_name }}</strong>
            <StatusBadge :status="task.status" />
          </div>
          <p class="muted">{{ task.message }}</p>
          <div class="button-row">
            <button class="button button-ghost" :disabled="!task.raw_result_ready" @click="ezdfsStore.downloadRaw(task.task_id)">
              Raw Data
            </button>
            <button class="button button-secondary" @click="ezdfsStore.generateSummary(task.task_id)">결과서 생성</button>
            <button
              class="button button-accent"
              :disabled="!task.summary_result_ready"
              @click="ezdfsStore.downloadSummary(task.task_id)"
            >
              결과서 다운로드
            </button>
          </div>
        </div>
        <p v-if="!tasks.length" class="muted">아직 등록된 ezDFS 작업이 없습니다.</p>
      </div>
    </article>
  </section>
</template>

