<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['logged-in'])

const auth = useAuthStore()
const password = ref('')
const remember = ref(false)
const error = ref('')

onMounted(() => {
  if (auth.savedPassword) {
    password.value = auth.savedPassword
    remember.value = true
  }
})

async function handleLogin() {
  error.value = ''
  if (!password.value) {
    error.value = '请输入密码'
    return
  }

  const result = await auth.login(password.value, remember.value)
  if (result.success) {
    emit('logged-in')
  } else {
    error.value = result.error || '登录失败'
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    handleLogin()
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Left Side - Login Form -->
    <div class="login-left">
      <div class="login-container">
        <div class="login-header">
          <div class="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
              <line x1="6" y1="6" x2="6.01" y2="6"/>
              <line x1="6" y1="18" x2="6.01" y2="18"/>
            </svg>
          </div>
          <h1 class="brand">easyNas</h1>
          <p class="tagline">简单高效的网络存储解决方案</p>
        </div>

        <!-- Login Form -->
        <div v-if="!auth.mustChangePassword" class="login-form">
          <div class="form-title">用户登录</div>
          <div class="form-group">
            <input
              type="password"
              v-model="password"
              placeholder="请输入密码"
              class="form-input"
              @keydown="handleKeydown"
              autofocus
            />
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <div class="remember-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="remember" />
              <span>记住密码</span>
            </label>
          </div>

          <button class="btn btn-primary" @click="handleLogin" :disabled="auth.loading">
            <span v-if="auth.loading">登录中...</span>
            <span v-else>登 录</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Right Side - Branding -->
    <div class="login-right">
      <div class="features">
        <div class="feature-item">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </div>
          <span>高速下载</span>
        </div>
        <div class="feature-item">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <span>文件管理</span>
        </div>
        <div class="feature-item">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="18" cy="5" r="3"/>
              <circle cx="6" cy="12" r="3"/>
              <circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
          </div>
          <span>网络共享</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  background: var(--bg);
}

/* Left Side */
.login-left {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  padding: 40px;
}

.login-container {
  width: 100%;
  max-width: 360px;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
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
  width: 40px;
  height: 40px;
  color: white;
}

.brand {
  font-size: 32px;
  font-weight: 700;
  color: var(--fg);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.tagline {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.form-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--fg);
  margin-bottom: 24px;
  text-align: center;
}

.login-form,
.change-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.form-input {
  width: 100%;
  padding: 14px 16px;
  border: 2px solid var(--border);
  border-radius: 12px;
  background: var(--bg);
  color: var(--fg);
  font-size: 15px;
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
}

.form-input::placeholder {
  color: var(--muted);
}

.error-message {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  padding: 10px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 8px;
}

.remember-row {
  display: flex;
  justify-content: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--muted);
}

.checkbox-label input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Right Side - Branding */
.login-right {
  flex: 1.2;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 50%, #16162a 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
}

/* Background decoration */
.login-right::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(ellipse at 30% 70%, rgba(99, 102, 241, 0.2) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 30%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 60%);
  animation: pulse 15s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.05); }
}

.features {
  display: flex;
  gap: 60px;
  justify-content: center;
  align-items: center;
  position: relative;
  z-index: 1;
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.feature-icon {
  width: 64px;
  height: 64px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.feature-icon svg {
  width: 30px;
  height: 30px;
  color: rgba(255, 255, 255, 0.9);
}

.feature-item span {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* Responsive */
@media (max-width: 900px) {
  .login-page {
    flex-direction: column;
  }

  .login-right {
    display: none;
  }

  .login-left {
    min-height: 100vh;
  }
}
</style>
