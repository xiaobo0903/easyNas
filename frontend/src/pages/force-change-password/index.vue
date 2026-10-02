<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleChangePassword() {
  error.value = ''

  if (!oldPassword.value) {
    error.value = '请输入旧密码'
    return
  }
  if (!newPassword.value) {
    error.value = '请输入新密码'
    return
  }
  if (newPassword.value.length < 6) {
    error.value = '新密码长度不能少于6位'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  const result = await auth.changePassword(oldPassword.value, newPassword.value)
  loading.value = false

  if (result.success) {
    message.success('密码修改成功')
    // Navigate to main page
    router.push('/')
  } else {
    error.value = result.error || '修改失败'
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    handleChangePassword()
  }
}
</script>

<template>
  <div class="force-change-page">
    <div class="change-card">
      <div class="logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <h1 class="brand">easyNas</h1>
      <h2 class="title">首次登录 · 修改密码</h2>
      <p class="subtitle">为了保障账户安全，请修改您的登录密码</p>

      <div class="form">
        <div class="form-group">
          <label>旧密码</label>
          <NInput
            type="password"
            v-model:value="oldPassword"
            placeholder="请输入旧密码"
            @keydown="handleKeydown"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label>新密码</label>
          <NInput
            type="password"
            v-model:value="newPassword"
            placeholder="请输入新密码（至少6位）"
            @keydown="handleKeydown"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label>确认密码</label>
          <NInput
            type="password"
            v-model:value="confirmPassword"
            placeholder="请再次输入新密码"
            @keydown="handleKeydown"
            :disabled="loading"
          />
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <NButton
          type="primary"
          block
          @click="handleChangePassword"
          :loading="loading"
          :disabled="loading"
        >
          {{ loading ? '处理中...' : '确认修改' }}
        </NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.force-change-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 50%, #16162a 100%);
  position: relative;
  overflow: hidden;
}

.force-change-page::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(ellipse at 30% 70%, rgba(99, 102, 241, 0.2) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 30%, rgba(139, 92, 246, 0.15) 0%, transparent 50%);
  animation: pulse 15s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.05); }
}

.change-card {
  background: var(--surface);
  border-radius: 20px;
  padding: 48px;
  max-width: 400px;
  width: 100%;
  text-align: center;
  position: relative;
  z-index: 1;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.logo {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 40px rgba(99, 102, 241, 0.3);
}

.logo svg {
  width: 36px;
  height: 36px;
  color: white;
}

.brand {
  font-size: 28px;
  font-weight: 700;
  color: var(--fg);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.title {
  font-size: 22px;
  font-weight: 600;
  color: var(--fg);
  margin: 24px 0 8px;
}

.subtitle {
  font-size: 14px;
  color: var(--muted);
  margin: 0 0 32px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: left;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
}

.error-message {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  padding: 10px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 8px;
}
</style>
