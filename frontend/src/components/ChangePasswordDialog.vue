<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'changed'])

const auth = useAuthStore()
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
    ElMessage.success('密码修改成功')
    resetForm()
    emit('changed')
    emit('close')
  } else {
    error.value = result.error || '修改失败'
  }
}

function resetForm() {
  oldPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  error.value = ''
}

function handleClose() {
  resetForm()
  emit('close')
}
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    title="修改密码"
    width="400px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="change-password-form">
      <div class="form-group">
        <label>旧密码</label>
        <input type="password" v-model="oldPassword" class="form-input" placeholder="请输入旧密码" />
      </div>

      <div class="form-group">
        <label>新密码</label>
        <input type="password" v-model="newPassword" class="form-input" placeholder="请输入新密码（至少6位）" />
      </div>

      <div class="form-group">
        <label>确认密码</label>
        <input type="password" v-model="confirmPassword" class="form-input" placeholder="请再次输入新密码" @keyup.enter="handleSubmit" />
      </div>

      <div v-if="error" class="error-message">
        {{ error }}
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="loading">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.change-password-form {
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
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--fg);
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
}

.error-message {
  color: var(--danger);
  font-size: 13px;
  padding: 8px 12px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 6px;
}
</style>
