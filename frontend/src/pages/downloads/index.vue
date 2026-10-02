<script setup>
import { ref } from 'vue'
import { NButton, NSpace, NCheckbox, useMessage } from 'naive-ui'
import { useTaskStore } from '../../stores/tasks'
import TaskTable from '../../components/TaskTable.vue'
import AddTaskModal from '../../components/AddTaskModal.vue'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

const store = useTaskStore()
const message = useMessage()
const showModal = ref(false)
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
</script>

<template>
  <div class="downloads-page">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="toolbar-select">
          <NCheckbox
            :checked="store.selectedIds.size === store.activeTasks.length && store.activeTasks.length > 0"
            @update:checked="(checked) => checked ? store.selectAll() : store.clearSelection()"
          />
          <span>全选</span>
        </div>
        <NSpace>
          <NButton size="small" @click="store.bulkPause" :disabled="store.selectedIds.size === 0">暂停</NButton>
          <NButton size="small" @click="store.bulkResume" :disabled="store.selectedIds.size === 0">开始</NButton>
          <NButton size="small" type="error" @click="handleBulkDelete" :disabled="store.selectedIds.size === 0">删除</NButton>
        </NSpace>
      </div>
      <NButton type="primary" @click="showModal = true">新增任务</NButton>
    </div>

    <!-- Task Table -->
    <TaskTable :tasks="store.activeTasks" :show-completed-actions="false" />

    <!-- Add Task Modal -->
    <AddTaskModal v-if="showModal" @close="showModal = false" @added="store.fetchTasks" />

    <!-- Bulk Delete Dialog -->
    <ConfirmDialog
      ref="bulkDeleteDialogRef"
      title="确认删除"
      confirm-text="删除"
      cancel-text="取消"
      :show-dont-ask-again="true"
    />
  </div>
</template>

<style scoped>
.downloads-page {
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
