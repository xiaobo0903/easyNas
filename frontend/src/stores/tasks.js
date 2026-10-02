import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskAPI, settingsAPI } from '../api'

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)
  const selectedIds = ref(new Set())
  const settings = ref({
    maxConcurrent: 5,
    deleteConfirm: true,
    deleteWithFiles: true,
    savePath: 'downloads',
  })

  // 本地待保存的设置（未点击保存按钮前）
  const pendingSettings = ref({
    maxConcurrent: 5,
    deleteConfirm: true,
    deleteWithFiles: true,
    savePath: 'downloads',
  })

  // 是否有待保存的修改
  const hasPendingChanges = computed(() => {
    return JSON.stringify(pendingSettings.value) !== JSON.stringify(settings.value)
  })

  const activeTasks = computed(() => tasks.value.filter(t => t.status !== 'completed' && t.status !== 'failed'))
  const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed' || t.status === 'failed'))
  const failedTasks = computed(() => tasks.value.filter(t => t.status === 'failed'))

  async function fetchSettings() {
    try {
      const res = await settingsAPI.get()
      settings.value = res.data
      pendingSettings.value = { ...res.data }
    } catch (e) {
      console.error('Failed to fetch settings:', e)
    }
  }

  // 初始化待保存设置为当前已保存的设置
  function initPendingSettings() {
    pendingSettings.value = { ...settings.value }
  }

  // 更新待保存的设置（本地预览用，不实际保存）
  function updatePendingSettings(newSettings) {
    pendingSettings.value = { ...pendingSettings.value, ...newSettings }
  }

  // 保存设置到服务器
  async function saveSettings() {
    try {
      await settingsAPI.update(pendingSettings.value)
      settings.value = { ...pendingSettings.value }
    } catch (e) {
      console.error('Failed to save settings:', e)
      throw e
    }
  }

  // 重置待保存的设置
  function resetPendingSettings() {
    pendingSettings.value = { ...settings.value }
  }

  async function updateSettings(newSettings) {
    try {
      await settingsAPI.update(newSettings)
      settings.value = { ...settings.value, ...newSettings }
      pendingSettings.value = { ...pendingSettings.value, ...newSettings }
    } catch (e) {
      console.error('Failed to update settings:', e)
      throw e
    }
  }

  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      const res = await taskAPI.list()
      tasks.value = res.data.tasks || []
    } catch (e) {
      error.value = e.message
      console.error('Failed to fetch tasks:', e)
    } finally {
      loading.value = false
    }
  }

  async function addTask(url, name, savePath) {
    loading.value = true
    error.value = null
    try {
      const res = await taskAPI.add({ url, name, savePath })
      tasks.value.push(res.data)
      return res.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function pauseTask(id) {
    // Immediately update UI
    const task = tasks.value.find(t => t.id === id)
    if (task) task.status = 'paused'
    // Then process in background
    try {
      await taskAPI.pause(id)
    } catch (e) {
      // Revert on error
      if (task) task.status = 'active'
      console.error('Failed to pause task:', e)
    }
  }

  async function resumeTask(id) {
    // Immediately update UI
    const task = tasks.value.find(t => t.id === id)
    if (task) task.status = 'active'
    // Then process in background
    try {
      await taskAPI.resume(id)
    } catch (e) {
      // Revert on error
      if (task) task.status = 'paused'
      console.error('Failed to resume task:', e)
    }
  }

  async function removeTask(id) {
    // Immediately remove from UI
    const taskIndex = tasks.value.findIndex(t => t.id === id)
    const removedTask = taskIndex >= 0 ? tasks.value[taskIndex] : null
    tasks.value = tasks.value.filter(t => t.id !== id)
    selectedIds.value.delete(id)
    // Then process in background
    try {
      await taskAPI.remove(id, settings.value.deleteWithFiles)
    } catch (e) {
      // Revert on error
      if (removedTask && taskIndex >= 0) {
        tasks.value.splice(taskIndex, 0, removedTask)
      }
      console.error('Failed to remove task:', e)
    }
  }

  async function pauseAll() {
    // Immediately update UI
    const originalStatuses = {}
    tasks.value.forEach(t => {
      if (t.status === 'active') {
        originalStatuses[t.id] = 'active'
        t.status = 'paused'
      }
    })
    // Then process in background
    try {
      await taskAPI.pauseAll()
    } catch (e) {
      // Revert on error
      Object.entries(originalStatuses).forEach(([id, status]) => {
        const task = tasks.value.find(t => t.id === id)
        if (task) task.status = status
      })
      console.error('Failed to pause all:', e)
    }
  }

  async function resumeAll() {
    // Immediately update UI
    const originalStatuses = {}
    tasks.value.forEach(t => {
      if (t.status === 'paused') {
        originalStatuses[t.id] = 'paused'
        t.status = 'active'
      }
    })
    // Then process in background
    try {
      await taskAPI.resumeAll()
    } catch (e) {
      // Revert on error
      Object.entries(originalStatuses).forEach(([id, status]) => {
        const task = tasks.value.find(t => t.id === id)
        if (task) task.status = status
      })
      console.error('Failed to resume all:', e)
    }
  }

  function toggleSelect(id) {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id)
    } else {
      selectedIds.value.add(id)
    }
  }

  function selectAll(taskList = null) {
    const list = taskList || tasks.value
    list.forEach(t => selectedIds.value.add(t.id))
  }

  function clearSelection() {
    selectedIds.value.clear()
  }

  function clearSelection() {
    selectedIds.value.clear()
  }

  async function bulkPause() {
    // Immediately update UI
    const selected = [...selectedIds.value]
    const pausedTasks = []
    selected.forEach(id => {
      const task = tasks.value.find(t => t.id === id)
      if (task && (task.status === 'active' || task.status === 'downloading')) {
        pausedTasks.push({ id, originalStatus: task.status })
        task.status = 'paused'
      }
    })
    clearSelection()
    // Then process in background - pause only selected tasks
    try {
      for (const { id } of pausedTasks) {
        await taskAPI.pause(id)
      }
    } catch (e) {
      // Revert on error
      pausedTasks.forEach(({ id, originalStatus }) => {
        const task = tasks.value.find(t => t.id === id)
        if (task) task.status = originalStatus
      })
      console.error('Failed to bulk pause:', e)
    }
  }

  async function bulkResume() {
    // Immediately update UI
    const selected = [...selectedIds.value]
    const resumedTasks = []
    selected.forEach(id => {
      const task = tasks.value.find(t => t.id === id)
      if (task && task.status === 'paused') {
        resumedTasks.push({ id, originalStatus: 'paused' })
        task.status = 'active'
      }
    })
    clearSelection()
    // Then process in background - resume only selected tasks
    try {
      for (const { id } of resumedTasks) {
        await taskAPI.resume(id)
      }
    } catch (e) {
      // Revert on error
      resumedTasks.forEach(({ id, originalStatus }) => {
        const task = tasks.value.find(t => t.id === id)
        if (task) task.status = originalStatus
      })
      console.error('Failed to bulk resume:', e)
    }
  }

  async function bulkRemove() {
    // Immediately update UI
    const selected = [...selectedIds.value]
    const removedTasks = []
    selected.forEach(id => {
      const taskIndex = tasks.value.findIndex(t => t.id === id)
      if (taskIndex >= 0) {
        removedTasks.push({ task: tasks.value[taskIndex], index: taskIndex })
      }
    })
    tasks.value = tasks.value.filter(t => !selectedIds.value.has(t.id))
    clearSelection()
    // Then process in background - API call per removed task
    try {
      const deleteFiles = settings.value.deleteWithFiles
      for (const id of selected) {
        await taskAPI.remove(id, deleteFiles)
      }
    } catch (e) {
      // Revert on error
      removedTasks.forEach(({ task, index }) => {
        tasks.value.splice(index, 0, task)
      })
      console.error('Failed to bulk remove:', e)
    }
  }

  async function clearCompletedTasks() {
    // Immediately update UI
    const completedIds = completedTasks.value.map(t => t.id)
    tasks.value = tasks.value.filter(t => t.status !== 'completed')
    // Then process in background
    try {
      await taskAPI.clearCompleted()
    } catch (e) {
      // Revert on error - re-add completed tasks
      console.error('Failed to clear completed tasks:', e)
    }
  }

  return {
    tasks,
    loading,
    error,
    selectedIds,
    settings,
    pendingSettings,
    hasPendingChanges,
    activeTasks,
    completedTasks,
    failedTasks,
    fetchTasks,
    fetchSettings,
    initPendingSettings,
    updatePendingSettings,
    saveSettings,
    resetPendingSettings,
    updateSettings,
    addTask,
    pauseTask,
    resumeTask,
    removeTask,
    pauseAll,
    resumeAll,
    toggleSelect,
    selectAll,
    clearSelection,
    bulkPause,
    bulkResume,
    bulkRemove,
    clearCompletedTasks,
  }
})
