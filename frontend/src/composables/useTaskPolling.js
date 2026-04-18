import { onBeforeUnmount, onMounted } from 'vue'

const TERMINAL_TASK_STATUSES = new Set(['DONE', 'FAIL', 'CANCELED'])

export function isTerminalTaskStatus(status) {
  return TERMINAL_TASK_STATUSES.has(String(status || '').toUpperCase())
}

export function useTaskPolling(tickFn, options = {}) {
  const intervalMs = options.intervalMs ?? 3000
  let timerId = null

  onMounted(() => {
    timerId = window.setInterval(() => {
      tickFn()
    }, intervalMs)
  })

  onBeforeUnmount(() => {
    if (timerId) {
      window.clearInterval(timerId)
      timerId = null
    }
  })
}

export async function waitForTaskTerminalStatus(tickFn, getMatchedTasks, taskIds, options = {}) {
  const timeoutMs = options.timeoutMs ?? 15 * 60 * 1000
  const intervalMs = options.intervalMs ?? 1500
  const timeoutMessage = options.timeoutMessage ?? '작업 완료 대기 시간이 초과되었습니다.'
  const startedAt = Date.now()

  const targetIds = Array.from(new Set((taskIds || []).filter(Boolean)))
  if (!targetIds.length) {
    return []
  }

  while (Date.now() - startedAt < timeoutMs) {
    await tickFn()

    const matched = getMatchedTasks(targetIds)
    if (matched.length === targetIds.length && matched.every((task) => isTerminalTaskStatus(task.status))) {
      return matched
    }

    await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
  }

  throw new Error(timeoutMessage)
}
