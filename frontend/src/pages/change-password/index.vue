<script setup>
import { ref } from 'vue'
import { NCard, NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const message = useMessage()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
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
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } else {
    error.value = result.error || '修改失败'
  }
}
</script>

<template>
  <div class="change-password-page">
    <NCard title="修改密码" class="change-password-card">
      <div class="form-group">
        <label>旧密码</label>
        <NInput
          type="password"
          v-model:value="oldPassword"
          placeholder="请输入旧密码"
          @keyup.enter="handleSubmit"
          show-password-on="mousedown"
        />
      </div>

      <div class="form-group">
        <label>新密码</label>
        <NInput
          type="password"
          v-model:value="newPassword"
          placeholder="请输入新密码（至少6位）"
          show-password-on="mousedown"
        />
      </div>

      <div class="form-group">
        <label>确认密码</label>
        <NInput
          type="password"
          v-model:value="confirmPassword"
          placeholder="请再次输入新密码"
          @keyup.enter="handleSubmit"
          show-password-on="mousedown"
        />
      </div>

      <div v-if="error" class="error-message">{{ error }}</div>

      <div class="form-actions">
        <NButton type="primary" block @click="handleSubmit" :loading="loading">
          确认修改
        </NButton>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.change-password-page {
  padding: 24px;
  max-width: 500px;
  margin: 0 auto;
}

.change-password-card {
  text-align: left;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
}

.form-group:last-of-type {
  margin-bottom: 0;
}

.error-message {
  color: var(--danger);
  font-size: 13px;
  padding: 10px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 8px;
  margin-top: 16px;
  text-align: center;
}

.form-actions {
  margin-top: 24px;
}
</style>
