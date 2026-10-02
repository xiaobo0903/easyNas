<script setup>
import { ref } from 'vue'
import { ElDialog } from 'element-plus'
import { useTaskStore } from '../stores/tasks'

const store = useTaskStore()

const visible = ref(false)
const dontAsk = ref(false)
const count = ref(0)
let resolveCallback = null

function open(msg, taskCount = 1) {
  count.value = taskCount
  if (!store.settings.deleteConfirm) {
    return Promise.resolve(true)
  }

  return new Promise((resolve) => {
    resolveCallback = resolve
    dontAsk.value = false
    visible.value = true
  })
}

function handleConfirm() {
  if (dontAsk.value) {
    store.updateSettings({ deleteConfirm: false })
  }
  visible.value = false
  if (resolveCallback) {
    resolveCallback(true)
    resolveCallback = null
  }
}

function handleCancel() {
  visible.value = false
  if (resolveCallback) {
    resolveCallback(false)
    resolveCallback = null
  }
}

defineExpose({ open })
</script>

<template>
  <ElDialog
    v-model="visible"
    title="确认删除"
    width="400"
    :close-on-click-modal="false"
    class="delete-confirm-dialog"
  >
    <div class="delete-content">
      <p class="delete-message">
        确定要删除{{ count > 1 ? `选中的 ${count} 个任务` : '这个任务' }}吗？
      </p>
      <div class="delete-checkbox">
        <input type="checkbox" id="dontAskDelete" v-model="dontAsk" />
        <label for="dontAskDelete">不再提示，直接删除！</label>
      </div>
    </div>
    <template #footer>
      <div class="delete-footer">
        <button class="btn btn-cancel" @click="handleCancel">取消</button>
        <button class="btn btn-delete" @click="handleConfirm">删除</button>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
:deep(.el-dialog__body) {
  text-align: left;
}

.delete-content {
  padding: 10px 0;
}

.delete-message {
  font-size: 14px;
  color: var(--fg);
  margin-bottom: 16px;
  text-align: left;
}

.delete-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.delete-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.delete-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}

.btn-cancel {
  background: var(--surface-hover);
  color: var(--fg);
}

.btn-cancel:hover {
  background: var(--border);
}

.btn-delete {
  background: var(--danger);
  color: white;
}

.btn-delete:hover {
  opacity: 0.9;
}
</style>

<style>
.delete-confirm-dialog .el-dialog__body {
  text-align: left;
}
</style>
