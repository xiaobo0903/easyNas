<script setup>
import { ref, reactive } from 'vue'
import { useTaskStore } from '../stores/tasks'
import { ElMessage } from 'element-plus'

const store = useTaskStore()
const saving = ref(false)

// 本地副本，初始从 store 复制
const form = reactive({
  maxConcurrent: store.settings.maxConcurrent,
  deleteConfirm: store.settings.deleteConfirm,
  deleteWithFiles: store.settings.deleteWithFiles,
  savePath: store.settings.savePath,
})

async function handleSave() {
  saving.value = true
  try {
    await store.updateSettings({
      maxConcurrent: form.maxConcurrent,
      deleteConfirm: form.deleteConfirm,
      deleteWithFiles: form.deleteWithFiles,
      savePath: form.savePath,
    })
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-panel">
    <div class="settings-section">
      <h3 class="section-title">下载设置</h3>

      <div class="setting-item">
        <div class="setting-label">
          <span class="label-text">最大并发数</span>
          <span class="label-value">{{ form.maxConcurrent }}</span>
        </div>
        <div class="setting-desc">同时下载的任务数量（5-15）</div>
        <el-slider v-model="form.maxConcurrent" :min="5" :max="15" :step="1" :show-tooltip="false" :marks="{ 5: '5', 10: '10', 15: '15' }" />
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">删除设置</h3>

      <div class="setting-item">
        <div class="setting-row">
          <div class="setting-info">
            <span class="label-text">删除确认</span>
            <span class="label-desc">删除任务时显示确认对话框</span>
          </div>
          <el-switch v-model="form.deleteConfirm" />
        </div>
      </div>

      <div class="setting-item">
        <div class="setting-row">
          <div class="setting-info">
            <span class="label-text">删除时删除文件</span>
            <span class="label-desc">删除任务时同时删除已下载的文件</span>
          </div>
          <el-switch v-model="form.deleteWithFiles" />
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">存储设置</h3>

      <div class="setting-item">
        <div class="setting-row">
          <div class="setting-info" style="flex: 1;">
            <span class="label-text">保存路径</span>
            <span class="label-desc">下载完成文件的保存目录</span>
            <input type="text" v-model="form.savePath" class="path-input" />
          </div>
        </div>
      </div>
    </div>

    <div class="settings-footer">
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存设置' }}
      </el-button>
    </div>

  </div>
</template>

<style scoped>
.settings-panel {
  padding: 24px;
  flex: 1;
}

.settings-section {
  margin-bottom: 32px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-bottom: 16px;
}

.setting-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
}

.setting-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.label-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
}

.label-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

.setting-desc {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 12px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.label-desc {
  font-size: 12px;
  color: var(--muted);
}

.path-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--fg);
  font-size: 13px;
  margin-top: 8px;
  box-sizing: border-box;
}

.path-input:focus {
  outline: none;
  border-color: var(--accent);
}

.settings-footer {
  max-width: 800px;
  margin: 0 auto;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
}

</style>
