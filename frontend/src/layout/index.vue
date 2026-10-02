<script setup>
import { ref, computed, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NIcon, NButton } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useTaskStore } from '../stores/tasks'
import {
  DownloadOutline,
  CheckmarkCircleOutline,
  SettingsOutline,
  FolderOutline,
  ShareOutline,
  LogOutOutline,
  KeyOutline
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const store = useTaskStore()

const collapsed = ref(false)

const menuOptions = [
  { label: '下载任务', key: '/downloads', icon: () => h(NIcon, null, { default: () => h(DownloadOutline) }) },
  { label: '已下载任务', key: '/completed', icon: () => h(NIcon, null, { default: () => h(CheckmarkCircleOutline) }) },
  { label: '任务设置', key: '/settings', icon: () => h(NIcon, null, { default: () => h(SettingsOutline) }) },
  { label: '文件管理', key: '/files', icon: () => h(NIcon, null, { default: () => h(FolderOutline) }) },
  { label: '共享设置', key: '/share', icon: () => h(NIcon, null, { default: () => h(ShareOutline) }) },
  { label: '修改密码', key: '/change-password', icon: () => h(NIcon, null, { default: () => h(KeyOutline) }) }
]

const activeKey = computed(() => route.path)
const pageTitle = computed(() => route.meta.title || 'easyNas')

let pollInterval = null

import { onMounted, onUnmounted } from 'vue'

onMounted(() => {
  store.fetchTasks()
  store.fetchSettings()
  pollInterval = setInterval(() => store.fetchTasks(), 3000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

function handleMenuUpdate(key) {
  router.push(key)
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <NLayout has-sider style="height: 100vh;">
    <!-- Sidebar -->
    <NLayoutSider
      bordered
      :width="170"
      :collapsed-width="12"
      :collapsed="collapsed"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="sidebar-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 28px; height: 28px;">
          <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
          <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
          <line x1="6" y1="6" x2="6.01" y2="6"/>
          <line x1="6" y1="18" x2="6.01" y2="18"/>
        </svg>
        <span v-if="!collapsed" class="logo-text">easyNas</span>
      </div>

      <NMenu
        :value="activeKey"
        :options="menuOptions"
        @update:value="handleMenuUpdate"
      />
    </NLayoutSider>

    <!-- Main Content Area -->
    <NLayout>
      <!-- Header -->
      <NLayoutHeader bordered>
        <div class="header-content">
          <span class="header-title">{{ pageTitle }}</span>
          <div class="header-actions">
          Exit
            <NIcon size="30" style="cursor: pointer;" @click="handleLogout">
              <LogOutOutline />
            </NIcon>
          </div>
        </div>
      </NLayoutHeader>

      <!-- Page Content -->
      <NLayoutContent content-style="padding: 16px 24px; background: var(--bg);">
        <router-view />
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

<style>
/* Theme Variables */
:root {
  --bg: #f5f5f7;
  --surface: #ffffff;
  --surface-hover: #e8e8ec;
  --fg: #1d1d1f;
  --muted: #6e6e73;
  --border: #d2d2d7;
  --accent: #0071e3;
  --accent-hover: #0077ed;
  --success: #34c759;
  --warning: #ff9f0a;
  --danger: #ff3b30;
  --radius: 8px;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
</style>

<style scoped>
.sidebar-logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid var(--border);
  color: var(--accent);
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.user-section {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px;
  border-top: 1px solid var(--border);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.user-name {
  font-size: 14px;
  color: var(--fg);
}

.header-content {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--fg);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name-header {
  font-size: 14px;
  color: var(--fg);
  margin-right: 8px;
}

/* Password Change Overlay */
.password-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.password-overlay-content {
  background: var(--surface);
  border-radius: 16px;
  padding: 48px;
  max-width: 400px;
  width: 100%;
  text-align: center;
}

.overlay-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 24px;
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.overlay-icon svg {
  width: 36px;
  height: 36px;
  color: white;
}

.password-overlay-content h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--fg);
  margin: 0 0 8px;
}

.password-overlay-content p {
  font-size: 14px;
  color: var(--muted);
  margin: 0 0 32px;
}

.change-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid var(--border);
  border-radius: 10px;
  background: var(--bg);
  color: var(--fg);
  font-size: 15px;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
}

.error-message {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  padding: 10px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 8px;
}

.btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Change Password Form */
.change-password-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Menu item spacing */
:deep(.n-menu) {
  padding: 8px;
}

:deep(.n-menu-item-content) {
  padding-left: 12px !important;
  padding-right: 12px !important;
  gap: 4px !important;
  justify-content: flex-start !important;
}

:deep(.n-menu-item-content__icon) {
  margin-right: 0 !important;
  flex-shrink: 0;
}

:deep(.n-menu-item-content__main) {
  flex-direction: row !important;
  justify-content: flex-start !important;
}

:deep(.n-menu-item-content__text) {
  font-size: 14px;
  text-align: left !important;
  margin-left: 0 !important;
}

:deep(.n-menu-item-content__extra) {
  display: none;
}

:deep(.n-menu-item-content::after) {
  display: none;
}
</style>
