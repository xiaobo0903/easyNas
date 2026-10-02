<script setup>
import { ref, onMounted } from 'vue'
import { NSwitch, NInput, NButton, NCard, useMessage } from 'naive-ui'
import { useTaskStore } from '../../stores/tasks'
import { shareAPI } from '../../api'

const store = useTaskStore()
const message = useMessage()
const shareStatus = ref({ installed: false, running: false, enabled: false })
const shareLoading = ref(false)
const savingSettings = ref(false)
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
      message.success('共享已开启')
    } else {
      await shareAPI.disable()
      message.success('共享已关闭')
    }
    // Update local settings state and refresh from server
    store.settings.shareEnabled = enabled
    await store.fetchSettings()
    await loadShareStatus()
    // Update local settings from store
    localSettings.value.shareName = store.settings.shareName || 'easynas'
    localSettings.value.shareDescription = store.settings.shareDescription || 'EasyNAS Download Share'
    localSettings.value.guestAccess = store.settings.guestAccess ?? true
    localSettings.value.shareUsername = store.settings.shareUsername || ''
    localSettings.value.shareReadOnly = store.settings.shareReadOnly ?? false
  } catch (e) {
    message.error(e.response?.data?.error || '操作失败')
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
    savingSettings.value = true
    await store.updateSettings(settings)
    message.success('共享设置已保存')
  } catch (e) {
    message.error('保存失败')
  } finally {
    savingSettings.value = false
  }
}
</script>

<template>
  <div class="share-page">
    <!-- Status Header -->
    <div class="share-status" :class="{ active: shareStatus.running }">
      <span class="status-dot"></span>
      <span class="status-text">{{ shareStatus.running ? '共享已开启' : '共享已关闭' }}</span>
    </div>

    <NCard title="网络共享" class="share-card">
      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">开启网络共享</span>
          <span class="setting-desc">
            通过 Samba 协议共享下载目录
            <span v-if="!shareStatus.installed" class="status-tag warning">未安装 Samba</span>
            <span v-else-if="shareStatus.running" class="status-tag success">运行中</span>
            <span v-else class="status-tag">已停止</span>
          </span>
        </div>
        <NSwitch
          :value="store.settings.shareEnabled"
          :loading="shareLoading"
          :disabled="!shareStatus.installed"
          @update:value="toggleShare"
        />
      </div>

      <div v-if="!shareStatus.installed" class="warning-text">
        Samba 未安装，请在终端运行：brew install samba
      </div>
    </NCard>

    <NCard title="共享设置" class="share-card" v-if="store.settings.shareEnabled">
      <div class="setting-item">
        <span class="setting-label">共享名称</span>
        <span class="setting-desc">网络上显示的共享文件夹名称</span>
        <NInput v-model:value="localSettings.shareName" placeholder="easynas" style="margin-top: 8px;" />
      </div>

      <div class="setting-item">
        <span class="setting-label">共享描述</span>
        <span class="setting-desc">对共享文件夹的描述说明</span>
        <NInput v-model:value="localSettings.shareDescription" placeholder="EasyNAS Download Share" style="margin-top: 8px;" />
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">访客访问</span>
          <span class="setting-desc">开启后无需用户名密码即可访问</span>
        </div>
        <NSwitch v-model:value="localSettings.guestAccess" />
      </div>

      <div class="setting-item" v-if="!localSettings.guestAccess">
        <span class="setting-label">用户名</span>
        <span class="setting-desc">访问共享的用户名</span>
        <NInput v-model:value="localSettings.shareUsername" placeholder="请输入用户名" style="margin-top: 8px;" />
      </div>

      <div class="setting-item" v-if="!localSettings.guestAccess">
        <span class="setting-label">密码</span>
        <span class="setting-desc">访问共享的密码（不填则保持原密码）</span>
        <NInput type="password" v-model:value="localSettings.sharePassword" placeholder="请输入密码" style="margin-top: 8px;" />
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <span class="setting-label">只读模式</span>
          <span class="setting-desc">开启后其他设备只能读取，不能修改删除文件</span>
        </div>
        <NSwitch v-model:value="localSettings.shareReadOnly" />
      </div>

      <div class="setting-item">
        <NButton type="primary" @click="saveShareSettings" :loading="savingSettings">保存设置</NButton>
      </div>
    </NCard>

    <NCard title="使用方法" class="share-card" v-if="store.settings.shareEnabled">
      <div class="usage-content">
        <p>共享开启后，在同一网络的设备上：</p>
        <div class="usage-item">
          <span class="usage-label">macOS:</span>
          <span>Finder → 前往 → 连接服务器 → <code>smb://本机IP</code></span>
        </div>
        <div class="usage-item">
          <span class="usage-label">Windows:</span>
          <span>文件资源管理器 → <code>\\本机IP</code></span>
        </div>
        <div class="usage-item">
          <span class="usage-label">手机:</span>
          <span>使用文件管理器添加 SMB 服务器</span>
        </div>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.share-page {
  padding: 24px;
  max-width: 700px;
  margin: 0 auto;
}

.share-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 16px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--muted);
}

.share-status.active .status-dot {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
}

.share-card {
  margin-bottom: 16px;
  text-align: left;
}

.setting-item {
  margin-bottom: 16px;
  text-align: left;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
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
}

.setting-desc {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  margin-left: 8px;
  background: var(--surface-hover);
  color: var(--muted);
}

.status-tag.success {
  background: color-mix(in srgb, var(--success) 15%, transparent);
  color: var(--success);
}

.status-tag.warning {
  background: color-mix(in srgb, var(--warning) 15%, transparent);
  color: var(--warning);
}

.warning-text {
  font-size: 12px;
  color: var(--warning);
  margin-top: 12px;
  padding: 10px 14px;
  background: color-mix(in srgb, var(--warning) 10%, transparent);
  border-radius: 6px;
}

.usage-content {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.8;
  text-align: left;
}

.usage-content p {
  margin-bottom: 12px;
}

.usage-item {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.usage-label {
  color: var(--fg);
  font-weight: 500;
  min-width: 70px;
}

.usage-content code {
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: var(--fg);
}
</style>
