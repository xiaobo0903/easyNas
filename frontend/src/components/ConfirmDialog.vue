<script setup>
import { ref } from 'vue'
import { ElDialog, ElCheckbox, ElButton } from 'element-plus'

const props = defineProps({
  title: {
    type: String,
    default: '确认'
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  showDontAskAgain: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel'])

const visible = ref(false)
const dontAskAgain = ref(false)
const resolvePromise = ref(null)
const dynamicMessage = ref('')

function show(message = '') {
  dynamicMessage.value = message
  dontAskAgain.value = false
  visible.value = true
  return new Promise((resolve) => {
    resolvePromise.value = resolve
  })
}

function handleConfirm() {
  visible.value = false
  if (resolvePromise.value) {
    resolvePromise.value({ confirmed: true, dontAskAgain: dontAskAgain.value })
  }
}

function handleCancel() {
  visible.value = false
  if (resolvePromise.value) {
    resolvePromise.value({ confirmed: false, dontAskAgain: false })
  }
}

defineExpose({ show })
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="title"
    width="400px"
    :close-on-click-modal="false"
    class="confirm-dialog"
    @closed="handleCancel"
  >
    <div class="dialog-content">
      <p class="dialog-message">{{ dynamicMessage }}</p>
      <div v-if="showDontAskAgain" class="dont-ask-again">
        <el-checkbox v-model="dontAskAgain">不再提示</el-checkbox>
      </div>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">{{ cancelText }}</el-button>
        <el-button type="danger" @click="handleConfirm">{{ confirmText }}</el-button>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.dialog-content {
  padding: 8px 0;
}

.dialog-message {
  font-size: 14px;
  color: var(--fg);
  line-height: 1.6;
  margin: 0;
  text-align: left;
}

.dont-ask-again {
  margin-top: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

<style>
.confirm-dialog .el-dialog__header {
  border-bottom: 1px solid var(--border);
  padding: 16px 20px;
  margin-right: 0;
}

.confirm-dialog .el-dialog__body {
  padding: 20px;
  text-align: left;
}

.confirm-dialog .el-dialog__footer {
  border-top: 1px solid var(--border);
  padding: 12px 20px;
}
</style>
