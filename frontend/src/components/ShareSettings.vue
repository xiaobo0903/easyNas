<script setup>
import { ref, onMounted } from 'vue'
import { useTaskStore } from '../stores/tasks'
import { shareAPI } from '../api'
import { ElMessage } from 'element-plus'

const store = useTaskStore()
const shareStatus = ref({ installed: false, running: false, enabled: false })
const shareLoading = ref(false)
const localSettings = ref({
  shareName: 'easynas',
  shareDescription: 'EasyNAS Download Share',
  guestAccess: true,
  shareUsername: '',
  sharePassword: '',
  shareReadOnly: false,
})

onMounted(async () => {
  await loadShareStatus()
  localSettings.value.shareName = store.settings.shareName || 'easynas'
  localSettings.value.shareDescription = store.settings.shareDescription || 'EasyNAS Download Share'
  localSettings.value.guestAccess = store.settings.guestAccess ?? true
  localSettings.value.shareUsername = store.settings.shareUsername || ''
  localSettings.value.shareReadOnly = store.settings.shareReadOnly ?? false
})

async function loadShareStatus() {
  try {
    const res = await shareAPI.getStatus()
    shareStatus.value = res.data
  } catch (e) {
    console.error('Failed to get share status', e)
  }
}

async function toggleShare(enabled) {
  shareLoading.value = true
  try {
    if (enabled) {
      await shareAPI.enable()
      ElMessage.success('共享已开启')
    } else {
      await shareAPI.disable()
      ElMessage.success('共享已关闭')
    }
    await loadShareStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
    store.settings.shareEnabled = !enabled
  } finally {
    shareLoading.value = false
  }
}

async function saveShareSettings() {
  const settings = {
    shareName: localSettings.value.shareName,
    shareDescription: localSettings.value.shareDescription,
    guestAccess: localSettings.value.guestAccess,
    shareUsername: localSettings.value.shareUsername,
    shareReadOnly: localSettings.value.shareReadOnly,
  }
  if (localSettings.value.sharePassword) {
    settings.sharePassword = localSettings.value.sharePassword
  }
  try {
    await store.updateSettings(settings)
    ElMessage.success('共享设置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  }
}
</script>

<template>
  <div class="share-settings">
    <div class="share-header">
      <div class="share-status-indicator" :class="{ active: shareStatus.running }">
        <span class="status-dot"></span>
        <span class="status-text">{{ shareStatus.running ? '共享已开启' : '共享已关闭' }}</span>
      </div>
    </div>

    <div class="share-content">
      <!-- Enable Toggle -->
      <div class="setting-card">
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-title">开启网络共享</span>
            <span class="setting-desc">通过 Samba 协议共享下载目录</span>
          </div>
          <el-switch
            v-model="store.settings.shareEnabled"
            :loading="shareLoading"
            :disabled="!shareStatus.installed"
            @change="toggleShare"
          />
        </div>
        <div v-if="!shareStatus.installed" class="warning-text">
          Samba 未安装，请在终端运行：brew install samba
        </div>
      </div>

      <template v-if="store.settings.shareEnabled">
        <!-- Share Name -->
        <div class="setting-card">
          <div class="setting-info">
            <span class="setting-title">共享名称</span>
            <span class="setting-desc">网络上显示的共享文件夹名称</span>
            <input type="text" v-model="localSettings.shareName" class="form-input" placeholder="easynas" />
          </div>
        </div>

        <!-- Share Description -->
        <div class="setting-card">
          <div class="setting-info">
            <span class="setting-title">共享描述</span>
            <span class="setting-desc">对共享文件夹的描述说明</span>
            <input type="text" v-model="localSettings.shareDescription" class="form-input" placeholder="EasyNAS Download Share" />
          </div>
        </div>

        <!-- Access Type -->
        <div class="setting-card">
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-title">访客访问</span>
              <span class="setting-desc">开启后无需用户名密码即可访问</span>
            </div>
            <el-switch v-model="localSettings.guestAccess" />
          </div>
        </div>

        <!-- Username (if not guest) -->
        <div class="setting-card" v-if="!localSettings.guestAccess">
          <div class="setting-info">
            <span class="setting-title">用户名</span>
            <span class="setting-desc">访问共享的用户名</span>
            <input type="text" v-model="localSettings.shareUsername" class="form-input" placeholder="请输入用户名" />
          </div>
        </div>

        <!-- Password (if not guest) -->
        <div class="setting-card" v-if="!localSettings.guestAccess">
          <div class="setting-info">
            <span class="setting-title">密码</span>
            <span class="setting-desc">访问共享的密码（不填则保持原密码）</span>
            <input type="password" v-model="localSettings.sharePassword" class="form-input" placeholder="请输入密码" autocomplete="new-password" />
          </div>
        </div>

        <!-- Read Only -->
        <div class="setting-card">
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-title">只读模式</span>
              <span class="setting-desc">开启后其他设备只能读取，不能修改删除文件</span>
            </div>
            <el-switch v-model="localSettings.shareReadOnly" />
          </div>
        </div>

        <!-- Save Button -->
        <div class="setting-card">
          <button class="btn btn-primary" @click="saveShareSettings">
            保存设置
          </button>
        </div>

        <!-- Usage Info -->
        <div class="setting-card info-card">
          <div class="info-title">使用方法</div>
          <div class="info-text">
            共享开启后，在同一网络的设备上：
          </div>
          <div class="usage-item">
            <span class="usage-label">macOS:</span>
            <span class="usage-value">Finder → 前往 → 连接服务器 → <code>smb://本机IP</code></span>
          </div>
          <div class="usage-item">
            <span class="usage-label">Windows:</span>
            <span class="usage-value">文件资源管理器 → <code>\\本机IP</code></span>
          </div>
          <div class="usage-item">
            <span class="usage-label">手机:</span>
            <span class="usage-value">使用文件管理器添加 SMB 服务器</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.share-settings {
  padding: 24px;
  max-width: 700px;
  margin: 0 auto;
}

.share-header {
  margin-bottom: 24px;
}

.share-status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--muted);
}

.share-status-indicator.active .status-dot {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
}

.share-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.setting-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.setting-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
}

.setting-desc {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--fg);
  font-size: 13px;
  margin-top: 10px;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
}

.warning-text {
  font-size: 12px;
  color: var(--warning);
  margin-top: 10px;
  padding: 8px 12px;
  background: color-mix(in srgb, var(--warning) 10%, transparent);
  border-radius: 6px;
}

.info-card {
  background: color-mix(in srgb, var(--accent) 8%, var(--surface));
  border-color: color-mix(in srgb, var(--accent) 20%, transparent);
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 12px;
}

.info-text {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 16px;
}

.usage-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 13px;
}

.usage-label {
  color: var(--fg);
  font-weight: 500;
  min-width: 70px;
}

.usage-value {
  color: var(--muted);
}

.usage-value code {
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: var(--fg);
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--radius);
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover {
  background: var(--accent-hover);
}
</style>
