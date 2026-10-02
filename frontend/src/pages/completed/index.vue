<script setup>
import { ref } from 'vue'
import { NButton, NSpace, NCheckbox } from 'naive-ui'
import { useTaskStore } from '../../stores/tasks'
import TaskTable from '../../components/TaskTable.vue'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

const store = useTaskStore()
const bulkDeleteDialogRef = ref(null)

async function handleBulkDelete() {
  if (store.selectedIds.size === 0) return
  const count = store.selectedIds.size
  if (!store.settings.deleteConfirm) {
    store.bulkRemove()
    return
  }
  const result = await bulkDeleteDialogRef.value.show(`确定要删除选中的 ${count} 个任务吗？`)
  if (result.confirmed) {
    if (result.dontAskAgain) {
      store.updateSettings({ deleteConfirm: false })
    }
    store.bulkRemove()
  }
}

function handleClearCompleted() {
  store.clearCompletedTasks()
}
</script>

<template>
  <div class="completed-page">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="toolbar-select">
          <NCheckbox
            :checked="store.selectedIds.size === store.completedTasks.length && store.completedTasks.length > 0"
            @update:checked="(checked) => checked ? store.selectAll() : store.clearSelection()"
          />
          <span>全选</span>
        </div>
        <NSpace>
          <NButton size="small" type="error" @click="handleBulkDelete" :disabled="store.selectedIds.size === 0">删除</NButton>
        </NSpace>
      </div>
      <NButton type="warning" @click="handleClearCompleted">清除记录</NButton>
    </div>

    <!-- Task Table -->
    <TaskTable :tasks="store.completedTasks" :show-completed-actions="true" />
  </div>
</template>

<style scoped>
.completed-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  background: var(--surface);
  border-radius: 8px;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-select {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 14px;
}
</style>
