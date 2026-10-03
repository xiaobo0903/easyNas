<script setup>
import { computed, ref } from 'vue'
import { useTaskStore } from '../stores/tasks'
import ConfirmDialog from './ConfirmDialog.vue'

const props = defineProps({
  tasks: {
    type: Array,
    default: () => []
  },
  showCompletedActions: {
    type: Boolean,
    default: false
  }
})

const store = useTaskStore()
const deleteDialogRef = ref(null)

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}

function formatSpeedWithLabel(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return ''
  return `${formatSize(bytesPerSec)}/s`
}

function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return ''
  return `${formatSize(bytesPerSec)}/s`
}

function formatTimeRemaining(bytesRemaining, bytesPerSec) {
  if (!bytesRemaining || bytesRemaining <= 0 || !bytesPerSec || bytesPerSec <= 0) return '—'
  const seconds = Math.ceil(bytesRemaining / bytesPerSec)
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}天${String(h).padStart(2, '0')}时${String(m).padStart(2, '0')}分`
  if (h > 0) return `${h}时${String(m).padStart(2, '0')}分`
  return `${m}分`
}

function formatCompletedTime(timestamp) {
  if (!timestamp) return '—'
  const date = new Date(timestamp * 1000)
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${m}-${d} ${h}:${min}`
}

function getStatusClass(status) {
  const map = {
    active: 'status-downloading',
    downloading: 'status-downloading',
    paused: 'status-paused',
    completed: 'status-completed',
    failed: 'status-failed',
    error: 'status-failed',
    idle: 'status-paused',
  }
  return map[status] || 'status-downloading'
}

function getStatusText(status) {
  const map = {
    active: '下载中',
    downloading: '下载中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    error: '失败',
    idle: '队列中',
  }
  return map[status] || status
}

function isSelected(id) {
  return store.selectedIds.has(id)
}

function handleSelectAll(e) {
  if (e.target.checked) {
    store.selectAll()
  } else {
    store.clearSelection()
  }
}

async function handleDelete(taskId) {
  if (!store.settings.deleteConfirm) {
    store.removeTask(taskId)
    return
  }
  const result = await deleteDialogRef.value.show('确定要删除这个任务吗？')
  if (!result.confirmed) return
  if (result.dontAskAgain) {
    store.updateSettings({ deleteConfirm: false })
  }
  store.removeTask(taskId)
}
</script>

<template>
  <div class="task-container">
    <table class="task-table" v-if="tasks.length > 0">
      <thead>
        <tr>
          <th class="col-check">
            <input type="checkbox" @change="handleSelectAll" :checked="store.selectedIds.size === tasks.length && tasks.length > 0" />
          </th>
          <th class="col-name">文件名</th>
          <th class="col-progress">进度</th>
          <th class="col-status">状态</th>
          <th class="col-time">完成时间</th>
          <th class="col-actions">&nbsp;&nbsp;&nbsp;操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.id" :data-id="task.id">
          <td class="col-check">
            <input type="checkbox" class="task-check" :checked="isSelected(task.id)" @change="store.toggleSelect(task.id)" />
          </td>
          <td class="col-name">
            <div class="task-name">{{ task.name || 'Untitled' }}</div>
            <div v-if="task.status === 'idle' && task.errorMsg" class="task-hint">{{ task.errorMsg }}</div>
            <div class="task-url">{{ task.url }}</div>
            <div class="task-info">
              <span class="task-size">{{ formatSize(task.downloaded) }} / {{ formatSize(task.totalSize) }}</span>
              <span v-if="task.speed > 0" class="task-speed">下载: {{ formatSpeedWithLabel(task.speed) }}</span>
              <span v-if="task.uploadSpeed > 0" class="task-speed upload">上传: {{ formatSpeedWithLabel(task.uploadSpeed) }}</span>
            </div>
          </td>
          <td class="col-progress">
            <div class="progress-wrap">
              <div class="progress-bar">
                <div class="progress-fill" :class="{ done: task.status === 'completed' }" :style="{ width: task.progress + '%' }"></div>
              </div>
              <span class="progress-text">{{ task.progress.toFixed(0) }}%</span>
            </div>
          </td>
          <td class="col-status">
            <span class="status" :class="getStatusClass(task.status)">
              <span class="status-dot"></span>
              {{ getStatusText(task.status) }}
            </span>
          </td>
          <td class="col-time">
            <span class="time-text">{{ showCompletedActions ? formatCompletedTime(task.completedAt) : formatTimeRemaining(task.totalSize - task.downloaded, task.speed) }}</span>
          </td>
          <td class="col-actions">
            <div class="row-actions">
              <button v-if="!showCompletedActions && (task.status === 'active' || task.status === 'downloading' || task.status === 'idle' || task.status === 'seeding')" class="icon-btn" title="暂停" @click="store.pauseTask(task.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
                </svg>
              </button>
              <button v-if="!showCompletedActions && task.status === 'paused'" class="icon-btn" title="开始" @click="store.resumeTask(task.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
              </button>
              <button class="icon-btn danger" title="删除" @click="handleDelete(task.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                </svg>
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Empty state -->
    <div class="empty" v-else>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <p>暂无下载任务</p>
    </div>

    <!-- Delete confirmation dialog -->
    <ConfirmDialog
      ref="deleteDialogRef"
      title="确认删除"
      confirm-text="删除"
      cancel-text="取消"
      :show-dont-ask-again="true"
    />
  </div>
</template>

<style scoped>
.task-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

.task-table {
  width: 100%;
  border-collapse: collapse;
}

.task-table th {
  text-align: left;
  padding: 10px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
}

.task-table td {
  text-align: left;
  padding: 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.task-table tr:hover td { background: var(--surface); }
.task-table tr:last-child td { border-bottom: none; }

.col-check { width: 40px; text-align: left; }
.col-name { min-width: 100px; flex: 1; text-align: left; }
.col-progress { width: 140px; text-align: left; }
.col-status { width: 90px; text-align: left; }
.col-time { width: 140px; text-align: left; }
.col-actions { width: 100px; flex-shrink: 0; text-align: left; }

.row-actions {
  display: flex;
  gap: 4px;
  align-items: center;
  justify-content: flex-start;
}

.task-name { font-weight: 500; text-align: left; }
.task-hint { font-size: 12px; color: #999; text-align: left; margin-top: 2px; }
.task-url { font-size: 11px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; text-align: left; }
.task-info { display: flex; gap: 8px; font-size: 11px; color: var(--muted); margin-top: 2px; flex-wrap: wrap; }
.task-speed { color: var(--accent); }
.task-speed.upload { color: var(--muted); }

.progress-wrap { display: flex; align-items: center; gap: 6px; }
.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-fill.done { background: var(--success); }
.progress-text { font-size: 10px; color: var(--muted); min-width: 28px; text-align: left; font-variant-numeric: tabular-nums; }

.time-text { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; text-align: left; }

.status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  text-align: left;
  font-weight: 500;
}

.status-downloading { background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); }
.status-paused { background: color-mix(in srgb, var(--warning) 15%, transparent); color: var(--warning); }
.status-completed { background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); }
.status-failed { background: color-mix(in srgb, var(--danger) 15%, transparent); color: var(--danger); }

.status-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-downloading .status-dot { animation: pulse 1.2s ease-in-out infinite; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.row-actions { display: flex; gap: 4px; justify-content: flex-end; }

.icon-btn {
  width: 30px; height: 30px;
  display: grid; place-items: center;
  border: none; background: transparent;
  color: var(--muted);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.icon-btn:hover { background: var(--surface-hover); color: var(--fg); }
.icon-btn.danger:hover { background: color-mix(in srgb, var(--danger) 15%, transparent); color: var(--danger); }
.icon-btn svg { width: 16px; height: 16px; }

.empty {
  text-align: center;
  padding: 80px 24px;
  color: var(--muted);
}

.empty svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.4; }
.empty p { font-size: 14px; }
</style>
