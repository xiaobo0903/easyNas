<script setup>
import { NSlider, NSwitch, NButton, NCard, useMessage } from 'naive-ui'
import { useTaskStore } from '../../stores/tasks'

const store = useTaskStore()
const message = useMessage()

function handleMaxConcurrentChange(val) {
  store.updatePendingSettings({ maxConcurrent: val })
}

function handleDeleteConfirmChange(val) {
  store.updateSettings({ deleteConfirm: val })
}

function handleDeleteWithFilesChange(val) {
  store.updateSettings({ deleteWithFiles: val })
}

async function handleSave() {
  try {
    await store.saveSettings()
    message.success('设置已保存')
  } catch (e) {
    message.error('保存失败')
  }
}

function handleReset() {
  store.resetPendingSettings()
  message.info('已重置')
}
</script>

<template>
  <div class="settings-page">
    <NCard title="下载设置" class="settings-card">
      <div class="setting-item">
        <div class="setting-header">
          <span class="setting-label">当前最大并发数: {{ store.pendingSettings.maxConcurrent }}</span>
        </div>
        <div class="setting-desc">同时下载的任务数量（5-15）</div>
        <NSlider
          :value="store.pendingSettings.maxConcurrent"
          :min="5"
          :max="15"
          :step="1"
          :marks="{ 5: '5', 10: '10', 15: '15' }"
          @update:value="handleMaxConcurrentChange"
        />
      </div>
    </NCard>

    <NCard title="删除设置" class="settings-card">
      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">删除确认</span>
          <span class="setting-desc">删除任务时显示确认对话框</span>
        </div>
        <NSwitch :value="store.pendingSettings.deleteConfirm" @update:value="handleDeleteConfirmChange" />
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">删除时删除文件</span>
          <span class="setting-desc">删除任务时同时删除已下载的文件</span>
        </div>
        <NSwitch :value="store.pendingSettings.deleteWithFiles" @update:value="handleDeleteWithFilesChange" />
      </div>
    </NCard>

    <NCard title="存储设置" class="settings-card">
      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">保存路径</span>
          <span class="setting-desc">下载完成文件的保存目录（固定为 ~/downloads）</span>
        </div>
        <span class="setting-value">~/downloads</span>
      </div>
    </NCard>

    <div class="settings-actions">
      <NButton @click="handleReset" :disabled="!store.hasPendingChanges">重置</NButton>
      <NButton type="primary" @click="handleSave" :disabled="!store.hasPendingChanges">保存设置</NButton>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.settings-card {
  text-align: left;
  margin-bottom: 16px;
}

.setting-item {
  margin-bottom: 16px;
  text-align: left;
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  gap: 12px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  gap: 16px;
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}

.setting-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
  text-align: left;
}

.setting-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
}

.setting-desc {
  font-size: 12px;
  color: var(--muted);
  text-align: left;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}
</style>
