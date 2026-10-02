<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { NButton, NInput, NModal, NTree, NDataTable, NUpload, NIcon, useMessage, useDialog, NSelect, NCheckbox } from 'naive-ui'
import { fileAPI } from '../../api'
import { useTaskStore } from '../../stores/tasks'

const message = useMessage()
const dialog = useDialog()
const store = useTaskStore()

const currentPath = ref('')
const items = ref([])
const loading = ref(false)
const selectedKeys = ref([])
const allSelected = ref(false)
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextMenuItem = ref(null)
const clipboard = ref({ action: null, paths: [] })

const renameDialogVisible = ref(false)
const renameOldPath = ref('')
const renameNewName = ref('')
const mkdirDialogVisible = ref(false)
const mkdirName = ref('')
const pasteDialogVisible = ref(false)
const pasteTargetPath = ref('')

const sortOrder = ref('name')

const sortOptions = [
  { label: '按名称', value: 'name' },
  { label: '按日期(升序)', value: 'date_asc' },
  { label: '按日期(降序)', value: 'date_desc' },
]

const breadcrumbs = ref([{ name: '根目录', path: '' }])

const columns = [
  { title: '文件名', key: 'name', render(row) { return row.name } },
  { title: '大小', key: 'size', width: 100 },
  { title: '修改时间', key: 'modifiedAt', width: 180 }
]

function hideContextMenu() {
  contextMenuVisible.value = false
}

function handleDocumentClick(e) {
  if (contextMenuVisible.value) {
    hideContextMenu()
  }
}

onMounted(() => {
  loadFiles()
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})

async function loadFiles() {
  loading.value = true
  selectedKeys.value = []
  allSelected.value = false
  try {
    const res = await fileAPI.list(currentPath.value, sortOrder.value)
    items.value = (res.data.items || []).map(item => ({
      ...item,
      key: item.path
    }))
  } catch (e) {
    message.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

function navigateTo(path) {
  currentPath.value = path
  updateBreadcrumbs()
  loadFiles()
}

function updateBreadcrumbs() {
  const parts = currentPath.value.split('/').filter(Boolean)
  breadcrumbs.value = [{ name: '根目录', path: '' }]
  let path = ''
  for (const part of parts) {
    path += '/' + part
    breadcrumbs.value.push({ name: part, path: path })
  }
}

function navigateUp() {
  if (!currentPath.value) return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  currentPath.value = parts.join('/')
  if (currentPath.value) currentPath.value = '/' + currentPath.value
  updateBreadcrumbs()
  loadFiles()
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedKeys.value = []
  } else {
    selectedKeys.value = items.value.map(item => item.path)
  }
  allSelected.value = !allSelected.value
}

function toggleSelect(row) {
  const index = selectedKeys.value.indexOf(row.path)
  if (index === -1) {
    selectedKeys.value.push(row.path)
  } else {
    selectedKeys.value.splice(index, 1)
  }
  allSelected.value = selectedKeys.value.length === items.value.length && items.value.length > 0
}

function handleContextMenu(e, row) {
  e.preventDefault()
  contextMenuItem.value = row
  if (!selectedKeys.value.includes(row.path)) {
    selectedKeys.value = [row.path]
  }
  contextMenuPosition.value = { x: e.clientX, y: e.clientY }
  contextMenuVisible.value = true
}

function handleRowClick(row) {
  if (row.isDir) {
    navigateTo(row.path)
  }
}

async function handleBatchPaste() {
  if (!clipboard.value.paths || clipboard.value.paths.length === 0) {
    message.warning('剪贴板为空')
    return
  }
  // 如果右键点击的是目录，则粘贴到该目录下；否则粘贴到当前目录
  const targetPath = contextMenuItem.value?.isDir ? contextMenuItem.value.path : currentPath.value
  try {
    if (clipboard.value.action === 'copy') {
      await fileAPI.copy(clipboard.value.paths, targetPath)
    } else {
      await fileAPI.move(clipboard.value.paths, targetPath)
    }
    clipboard.value = { action: null, paths: [] }
    loadFiles()
    message.success('操作成功')
  } catch (e) {
    message.error(e.response?.data?.error || '操作失败')
  }
}

function openRenameDialog(row) {
  renameOldPath.value = row.path
  renameNewName.value = row.name
  renameDialogVisible.value = true
}

async function handleRename() {
  if (!renameNewName.value.trim()) return
  try {
    await fileAPI.rename(renameOldPath.value, renameNewName.value)
    renameDialogVisible.value = false
    loadFiles()
    message.success('重命名成功')
  } catch (e) {
    message.error(e.response?.data?.error || '重命名失败')
  }
}

function openMkdirDialog() {
  contextMenuVisible.value = false
  mkdirName.value = ''
  mkdirDialogVisible.value = true
}

async function handleMkdir() {
  if (!mkdirName.value.trim()) return
  try {
    await fileAPI.mkdir(currentPath.value, mkdirName.value)
    mkdirDialogVisible.value = false
    loadFiles()
    message.success('创建成功')
  } catch (e) {
    message.error(e.response?.data?.error || '创建失败')
  }
}

function confirmDelete(paths) {
  const count = paths.length
  dialog.warning({
    title: '确认删除',
    content: `确定要删除这 ${count} 个项目吗？删除后无法恢复。`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => handleDelete(paths),
  })
}

async function handleDelete(paths) {
  try {
    await fileAPI.delete(paths)
    selectedKeys.value = []
    allSelected.value = false
    loadFiles()
    message.success('删除成功')
  } catch (e) {
    message.error(e.response?.data?.error || '删除失败')
  }
}

async function handleCopy() {
  if (selectedKeys.value.length === 0) return
  clipboard.value = { action: 'copy', paths: [...selectedKeys.value] }
  message.success('已复制到剪贴板')
}

async function handleCut() {
  if (selectedKeys.value.length === 0) return
  clipboard.value = { action: 'move', paths: [...selectedKeys.value] }
  message.success('已剪切到剪贴板')
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}

function formatDate(timestamp) {
  if (!timestamp) return '—'
  const date = new Date(timestamp * 1000)
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')} ${String(date.getHours()).padStart(2,'0')}:${String(date.getMinutes()).padStart(2,'0')}`
}
</script>

<template>
  <div class="files-page">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <NButton size="small" @click="navigateUp" :disabled="!currentPath">返回上级</NButton>
        <NButton size="small" @click="openMkdirDialog">新建文件夹</NButton>
        <NButton size="small" @click="loadFiles">刷新</NButton>
      </div>
      <div class="toolbar-right">
        <NSelect v-model:value="sortOrder" :options="sortOptions" size="small" style="width: 120px;" @update:value="loadFiles" />
      </div>
    </div>

    <!-- Breadcrumb -->
    <div class="breadcrumb">
      <span
        v-for="(crumb, index) in breadcrumbs"
        :key="crumb.path"
        @click="navigateTo(crumb.path)"
        :class="{ active: index === breadcrumbs.length - 1 }"
      >
        {{ crumb.name }}
        <span v-if="index < breadcrumbs.length - 1" class="separator">/</span>
      </span>
    </div>

    <!-- File List -->
    <div class="file-list" @click="selectedKeys = []; hideContextMenu()">
      <!-- Header with select all -->
      <div class="file-item header">
        <div class="file-checkbox" @click.stop="toggleSelectAll">
          <NCheckbox :checked="allSelected" />
        </div>
        <div class="file-icon"></div>
        <div class="file-info">
          <div class="file-name">文件名</div>
        </div>
        <div class="file-actions">
          <NButton size="small" type="error" :disabled="selectedKeys.length === 0" @click.stop="confirmDelete(selectedKeys)">删除选中</NButton>
        </div>
      </div>
      <div
        v-for="item in items"
        :key="item.path"
        class="file-item"
        :class="{ selected: selectedKeys.includes(item.path) }"
        @click="toggleSelect(item)"
        @contextmenu="handleContextMenu($event, item)"
        @dblclick="item.isDir && navigateTo(item.path)"
      >
        <div class="file-checkbox" @click.stop="toggleSelect(item)">
          <NCheckbox :checked="selectedKeys.includes(item.path)" />
        </div>
        <div class="file-icon">
          <svg v-if="item.isDir" viewBox="0 0 24 24" fill="currentColor">
            <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="file-info">
          <div class="file-name">{{ item.name }}</div>
          <div class="file-meta">
            <span v-if="!item.isDir">{{ formatSize(item.size) }}</span>
            <span>{{ formatDate(item.modifiedAt) }}</span>
          </div>
        </div>
      </div>

      <div v-if="items.length === 0 && !loading" class="empty">
        <p>文件夹为空</p>
      </div>
    </div>

    <!-- Context Menu -->
    <div
      v-if="contextMenuVisible"
      class="context-menu"
      :style="{ left: contextMenuPosition.x + 'px', top: contextMenuPosition.y + 'px' }"
    >
      <div class="context-item" @click="handleBatchPaste(); hideContextMenu()">粘贴</div>
      <div v-if="!contextMenuItem.isDir" class="context-item" @click="handleCopy(); hideContextMenu()">拷贝</div>
      <div v-if="!contextMenuItem.isDir" class="context-item" @click="handleCut(); hideContextMenu()">剪切</div>
      <div class="context-item" @click="openRenameDialog(contextMenuItem); hideContextMenu()">重命名</div>
      <div v-if="selectedKeys.length > 1" class="context-item danger" @click="confirmDelete(selectedKeys); hideContextMenu()">删除选中 ({{ selectedKeys.length }})</div>
      <div v-else class="context-item danger" @click="confirmDelete([contextMenuItem.path]); hideContextMenu()">删除</div>
    </div>

    <!-- Rename Dialog -->
    <NModal v-model:show="renameDialogVisible" preset="card" title="重命名" style="width: 400px;">
      <div class="dialog-content">
        <NInput v-model:value="renameNewName" placeholder="请输入新名称" @keyup.enter="handleRename" />
      </div>
      <template #footer>
        <NButton @click="renameDialogVisible = false">取消</NButton>
        <NButton type="primary" @click="handleRename">确定</NButton>
      </template>
    </NModal>

    <!-- Mkdir Dialog -->
    <NModal v-model:show="mkdirDialogVisible" preset="card" title="新建文件夹" style="width: 400px;">
      <div class="dialog-content">
        <NInput v-model:value="mkdirName" placeholder="请输入文件夹名称" @keyup.enter="handleMkdir" />
      </div>
      <template #footer>
        <NButton @click="mkdirDialogVisible = false">取消</NButton>
        <NButton type="primary" @click="handleMkdir">确定</NButton>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.files-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-radius: 8px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 8px;
}

.breadcrumb {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.breadcrumb span {
  cursor: pointer;
}

.breadcrumb span:hover {
  color: var(--accent);
}

.breadcrumb span.active {
  color: var(--fg);
  cursor: default;
}

.separator {
  margin: 0 8px;
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  gap: 12px;
  text-align: left;
}

.file-item.header {
  cursor: default;
  font-weight: 500;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
  padding-bottom: 8px;
}

.file-item.header:hover {
  background: transparent;
}

.file-item:hover {
  background: var(--surface-hover);
}

.file-item.selected {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
}

.file-checkbox {
  width: 24px;
  flex-shrink: 0;
}

.file-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}

.file-icon svg {
  width: 28px;
  height: 28px;
}

.file-info {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.file-name {
  font-size: 14px;
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}

.file-actions {
  margin-left: auto;
  flex-shrink: 0;
}

.file-meta {
  font-size: 12px;
  color: var(--muted);
  display: flex;
  gap: 16px;
  text-align: left;
}

.empty {
  text-align: center;
  padding: 40px;
  color: var(--muted);
}

.context-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  padding: 4px;
  z-index: 1000;
  min-width: 120px;
}

.context-item {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--fg);
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
}

.context-item:hover {
  background: var(--surface-hover);
}

.context-item.danger {
  color: var(--danger);
}

.dialog-content {
  padding: 16px 0;
}
</style>
