<script setup>
import { ref } from 'vue'
import { useTaskStore } from '../stores/tasks'

const emit = defineEmits(['close', 'added'])
const store = useTaskStore()

const url = ref('')
const name = ref('')
const savePath = ref('')
const submitting = ref(false)
const error = ref('')

async function handleSubmit() {
  if (!url.value.trim()) {
    error.value = '请输入下载链接'
    return
  }

  submitting.value = true
  error.value = ''

  try {
    await store.addTask(url.value.trim(), name.value.trim(), savePath.value.trim())
    emit('added')
    emit('close')
  } catch (e) {
    error.value = e.response?.data?.error || e.message || '添加失败'
  } finally {
    submitting.value = false
  }
}

function handleOverlayClick(e) {
  if (e.target === e.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">新增下载任务</span>
        <button class="modal-close" @click="$emit('close')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label" for="taskUrl">下载链接</label>
          <input
            type="text"
            id="taskUrl"
            v-model="url"
            class="form-input"
            placeholder="https://example.com/file.zip"
            @keydown.enter="handleSubmit"
            autofocus
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="taskName">文件名（可选）</label>
          <input
            type="text"
            id="taskName"
            v-model="name"
            class="form-input"
            placeholder="留空则自动从链接提取"
            @keydown.enter="handleSubmit"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="taskPath">保存路径（可选）</label>
          <input
            type="text"
            id="taskPath"
            v-model="savePath"
            class="form-input"
            placeholder="默认保存到下载目录"
            @keydown.enter="handleSubmit"
          />
        </div>
        <p class="form-hint">支持 HTTP/HTTPS/FTP/Magnet/Torrent/Thunder 链接</p>
        <p v-if="error" class="form-error">{{ error }}</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" @click="handleSubmit" :disabled="submitting">
          {{ submitting ? '添加中...' : '确定' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 580px;
  max-width: 90vw;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-title { font-size: 15px; font-weight: 600; }

.modal-close {
  width: 28px; height: 28px;
  display: grid; place-items: center;
  border: none; background: transparent;
  color: var(--muted);
  border-radius: 6px;
  cursor: pointer;
}

.modal-close:hover { background: var(--surface-hover); color: var(--fg); }
.modal-close svg { width: 18px; height: 18px; }

.modal-body { padding: 35px 20px; text-align: left; }

.form-group { margin-bottom: 16px; text-align: left; }

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
  margin-bottom: 6px;
}

.form-input {
  width: calc(100% - 60px);
  padding: 10px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--fg);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.form-input:focus { border-color: var(--accent); }
.form-input::placeholder { color: var(--muted); }

.form-hint { font-size: 11px; color: var(--muted); margin-top: 4px; }
.form-error { font-size: 12px; color: var(--danger); margin-top: 8px; }

.modal-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-secondary {
  background: var(--surface-hover);
  color: var(--fg);
  border: 1px solid var(--border);
}

.btn-secondary:hover { background: color-mix(in srgb, var(--fg) 10%, var(--surface)); }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius);
  border: none;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
