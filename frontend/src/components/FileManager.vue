<script setup>
import { ref, computed, onMounted } from 'vue'
import { fileAPI } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const emit = defineEmits(['refresh'])
const store = defineProps(['store'])

// State
const currentPath = ref('')
const items = ref([])
const loading = ref(false)
const selectedItems = ref(new Set())
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextMenuItem = ref(null)

// Clipboard for copy/paste
const clipboard = ref({ action: null, paths: [] })

// Dialogs
const renameDialogVisible = ref(false)
const renameOldPath = ref('')
const renameNewName = ref('')
const mkdirDialogVisible = ref(false)
const mkdirName = ref('')
const pasteDialogVisible = ref(false)
const pasteTargetPath = ref('')

// Breadcrumb
const breadcrumbs = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  const crumbs = [{ name: '根目录', path: '' }]
  let path = ''
  for (const part of parts) {
    path += '/' + part
    crumbs.push({ name: part, path: path })
  }
  return crumbs
})

// Format
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
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${h}:${min}`
}

function getItemIcon(item) {
  return item.isDir ? 'folder' : 'file'
}

// Load files
async function loadFiles() {
  loading.value = true
  selectedItems.value.clear()
  try {
    const res = await fileAPI.list(currentPath.value)
    items.value = res.data.items || []
  } catch (e) {
    ElMessage.error('加载文件列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// Navigation
function navigateTo(path) {
  currentPath.value = path
  loadFiles()
}

function navigateUp() {
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  currentPath.value = parts.join('/')
  if (currentPath.value) currentPath.value = '/' + currentPath.value
  loadFiles()
}

// Selection
function toggleSelect(item, e) {
  e.stopPropagation()
  if (selectedItems.value.has(item.path)) {
    selectedItems.value.delete(item.path)
  } else {
    selectedItems.value.add(item.path)
  }
  selectedItems.value = new Set(selectedItems.value)
}

function selectAll() {
  if (selectedItems.value.size === items.value.length) {
    selectedItems.value.clear()
  } else {
    items.value.forEach(item => selectedItems.value.add(item.path))
  }
  selectedItems.value = new Set(selectedItems.value)
}

function isSelected(path) {
  return selectedItems.value.has(path)
}

// Row click - folder: navigate into, file: select
function handleRowClick(item) {
  if (item.isDir) {
    navigateTo(item.path)
  } else {
    // Toggle selection for files
    toggleSelect(item, { stopPropagation: () => {} })
  }
}

// Context menu
function showContextMenu(e, item) {
  e.preventDefault()
  e.stopPropagation()
  contextMenuItem.value = item
  contextMenuPosition.value = { x: e.clientX, y: e.clientY }
  contextMenuVisible.value = true
}

function hideContextMenu() {
  contextMenuVisible.value = false
}

// Batch operations
async function handleBatchPaste() {
  if (clipboard.value.paths.length === 0) return
  try {
    const res = await fileAPI.copy(clipboard.value.paths, currentPath.value)
    if (res.data.errors?.length > 0) {
      ElMessage.error('部分粘贴失败')
    } else {
      ElMessage.success('粘贴成功')
    }
    clipboard.value = { action: null, paths: [] }
    loadFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '粘贴失败')
  }
}

async function handleBatchDelete() {
  if (selectedItems.value.size === 0) return
  const paths = [...selectedItems.value]
  const names = items.value.filter(i => paths.includes(i.path)).map(i => i.name)
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${paths.length} 个项目吗？${names.slice(0, 3).map(n => `"${n}"`).join(', ')}${names.length > 3 ? ' 等' : ''}？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await fileAPI.delete(paths)
    if (res.data.errors?.length > 0) {
      ElMessage.error('部分删除失败')
    } else {
      ElMessage.success('删除成功')
    }
    selectedItems.value.clear()
    loadFiles()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
    }
  }
}


// Rename
function openRenameDialog(item) {
  renameOldPath.value = item.path
  renameNewName.value = item.name
  renameDialogVisible.value = true
  hideContextMenu()
}

async function handleRename() {
  if (!renameNewName.value.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  try {
    await fileAPI.rename(renameOldPath.value, renameNewName.value.trim())
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    loadFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '重命名失败')
  }
}

// Create folder
function openMkdirDialog() {
  mkdirName.value = ''
  mkdirDialogVisible.value = true
  hideContextMenu()
}

async function handleMkdir() {
  if (!mkdirName.value.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  try {
    await fileAPI.mkdir(currentPath.value, mkdirName.value.trim())
    ElMessage.success('创建文件夹成功')
    mkdirDialogVisible.value = false
    loadFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '创建失败')
  }
}

// Delete
async function handleDelete(item) {
  hideContextMenu()
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${item.name}" 吗？${item.isDir ? '文件夹内的所有内容都将被删除。' : ''}`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await fileAPI.delete([item.path])
    if (res.data.errors?.length > 0) {
      ElMessage.error('删除失败')
    } else {
      ElMessage.success('删除成功')
    }
    loadFiles()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
    }
  }
}

async function handleBulkDelete() {
  if (selectedItems.value.size === 0) return
  const names = items.value.filter(i => selectedItems.value.has(i.path)).map(i => i.name)
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedItems.value.size} 个项目吗？${names.slice(0, 3).map(n => `"${n}"`).join(', ')}${names.length > 3 ? ' 等' : ''}？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await fileAPI.delete([...selectedItems.value])
    if (res.data.errors?.length > 0) {
      ElMessage.error('部分删除失败')
    } else {
      ElMessage.success('删除成功')
    }
    loadFiles()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
    }
  }
}

// Copy
function handleCopy(item) {
  hideContextMenu()
  // Just remember what to paste, don't create file yet
  clipboard.value = { action: 'copy', paths: [item.path], name: item.name }
  ElMessage.success(`已拷贝 "${item.name}"，右键目标文件夹粘贴`)
}

// Paste into directory
async function handlePasteInto(item) {
  hideContextMenu()
  if (clipboard.value.paths.length === 0) return
  try {
    const targetPath = item.path
    const res = await fileAPI.copy(clipboard.value.paths, targetPath)
    if (res.data.errors?.length > 0) {
      ElMessage.error('部分拷贝失败')
    } else {
      ElMessage.success('粘贴成功')
    }
    clipboard.value = { action: null, paths: [] }
    loadFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '粘贴失败')
  }
}

// Download
function handleDownload(item) {
  hideContextMenu()
  const link = document.createElement('a')
  link.href = `/api/files/download?path=${encodeURIComponent(item.path)}`
  link.download = item.name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Click outside to close context menu
function handleGlobalClick() {
  hideContextMenu()
}

onMounted(() => {
  loadFiles()
  document.addEventListener('click', handleGlobalClick)
})
</script>

<template>
  <div class="file-manager" @click="hideContextMenu">
    <!-- Header -->
    <div class="fm-header">
      <div class="fm-title">文件管理</div>
      <div class="fm-actions">
        <button class="btn btn-ghost" @click="openMkdirDialog" title="新建文件夹">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
          新建文件夹
        </button>
        <button class="btn btn-ghost" @click="handleBatchDelete" :disabled="selectedItems.size === 0" title="删除">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          删除{{ selectedItems.size > 0 ? ` (${selectedItems.size})` : '' }}
        </button>
      </div>
    </div>

    <!-- Breadcrumb & Path -->
    <div class="fm-path-bar">
      <button class="btn btn-ghost btn-sm" @click="navigateUp" :disabled="!currentPath">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <div class="breadcrumb">
        <span v-for="(crumb, idx) in breadcrumbs" :key="crumb.path">
          <span v-if="idx > 0" class="breadcrumb-sep">/</span>
          <a class="breadcrumb-item" :class="{ active: idx === breadcrumbs.length - 1 }" @click="navigateTo(crumb.path)">
            {{ crumb.name }}
          </a>
        </span>
      </div>
    </div>

    <!-- File List -->
    <div class="fm-content" v-loading="loading">
      <table class="fm-table" v-if="items.length > 0">
        <thead>
          <tr>
            <th class="col-check">
              <input type="checkbox" @change="selectAll" :checked="selectedItems.size === items.length && items.length > 0" />
            </th>
            <th class="col-name">名称</th>
            <th class="col-size">大小</th>
            <th class="col-date">修改时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.path"
              :class="{ selected: isSelected(item.path), 'folder-row': item.isDir }"
              @click="handleRowClick(item)"
              @contextmenu="showContextMenu($event, item)">
            <td class="col-check" @click.stop>
              <input type="checkbox" :checked="isSelected(item.path)" @click.stop="toggleSelect(item, $event)" />
            </td>
            <td class="col-name">
              <div class="item-name">
                <svg v-if="item.isDir" class="item-icon folder" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
                </svg>
                <svg v-else class="item-icon file" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="item-text">{{ item.name }}</span>
              </div>
            </td>
            <td class="col-size">{{ item.isDir ? '—' : formatSize(item.size) }}</td>
            <td class="col-date">{{ formatDate(item.modifiedAt) }}</td>
            <td class="col-actions" @click.stop>
              <div class="row-actions">
                <button class="icon-btn" title="重命名" @click="openRenameDialog(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button v-if="!item.isDir" class="icon-btn" title="下载" @click="handleDownload(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                </button>
                <button class="icon-btn danger" title="删除" @click="handleDelete(item)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty -->
      <div class="empty" v-else-if="!loading">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <p>此目录为空</p>
      </div>
    </div>

    <!-- Rename Dialog -->
    <el-dialog v-model="renameDialogVisible" title="重命名" width="400px">
      <div class="form-group">
        <label>新名称</label>
        <input type="text" v-model="renameNewName" class="form-input" @keyup.enter="handleRename" />
      </div>
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRename">确定</el-button>
      </template>
    </el-dialog>

    <!-- Mkdir Dialog -->
    <el-dialog v-model="mkdirDialogVisible" title="新建文件夹" width="400px">
      <div class="form-group">
        <label>文件夹名称</label>
        <input type="text" v-model="mkdirName" class="form-input" @keyup.enter="handleMkdir" placeholder="请输入文件夹名称" />
      </div>
      <template #footer>
        <el-button @click="mkdirDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleMkdir">创建</el-button>
      </template>
    </el-dialog>

    <!-- Context Menu -->
    <div v-if="contextMenuVisible" class="context-menu" :style="{ left: contextMenuPosition.x + 'px', top: contextMenuPosition.y + 'px' }">
      <div class="context-item" @click="openRenameDialog(contextMenuItem)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        重命名
      </div>
      <div class="context-item" @click="handleCopy(contextMenuItem)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        拷贝
      </div>
      <div v-if="contextMenuItem && contextMenuItem.isDir && clipboard.paths.length > 0" class="context-item" @click="handlePasteInto(contextMenuItem)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
        粘贴
      </div>
      <div v-if="contextMenuItem && !contextMenuItem.isDir" class="context-item" @click="handleDownload(contextMenuItem)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        下载
      </div>
      <div class="context-sep"></div>
      <div class="context-item danger" @click="handleDelete(contextMenuItem)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        删除
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
}

.fm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.fm-title {
  font-size: 14px;
  font-weight: 600;
}

.fm-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

.fm-path-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  flex-wrap: wrap;
}

.breadcrumb-sep {
  color: var(--muted);
}

.breadcrumb-item {
  color: var(--muted);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
}

.breadcrumb-item:hover {
  background: var(--surface-hover);
  color: var(--fg);
}

.breadcrumb-item.active {
  color: var(--fg);
  font-weight: 500;
  cursor: default;
}

.breadcrumb-item.active:hover {
  background: transparent;
}

.fm-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.fm-table {
  width: 100%;
  border-collapse: collapse;
}

.fm-table th {
  text-align: left;
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  background: var(--bg);
}

.fm-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.fm-table tr:hover td {
  background: var(--bg);
}

.fm-table tr.selected td {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}

.fm-table tr.folder-row {
  cursor: pointer;
}

.col-check { width: 40px; }
.col-name { min-width: 200px; }
.col-size { width: 100px; }
.col-date { width: 150px; }
.col-actions { width: 140px; }

.item-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.item-icon.folder {
  color: var(--warning);
}

.item-icon.file {
  color: var(--muted);
}

.item-text {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-actions {
  display: flex;
  gap: 4px;
}

.empty {
  text-align: center;
  padding: 60px 24px;
  color: var(--muted);
}

.empty svg {
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  opacity: 0.4;
}

.empty p {
  font-size: 14px;
}

/* Context Menu */
.context-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px;
  min-width: 160px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 9999;
}

.context-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--fg);
  border-radius: 4px;
  cursor: pointer;
}

.context-item:hover {
  background: var(--surface-hover);
}

.context-item.danger {
  color: var(--danger);
}

.context-item svg {
  width: 16px;
  height: 16px;
}

.context-sep {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

/* Form */
.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--fg);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.form-input:focus {
  border-color: var(--accent);
}

.form-hint {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  background: var(--surface);
  color: var(--fg);
}

.btn svg {
  width: 14px;
  height: 14px;
}

.btn:hover {
  background: var(--surface-hover);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 4px 8px;
}

.btn-sm svg {
  width: 16px;
  height: 16px;
}

.btn-ghost {
  background: transparent;
  border-color: var(--border);
}

.icon-btn {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--muted);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.icon-btn:hover {
  background: var(--surface-hover);
  color: var(--fg);
}

.icon-btn.danger:hover {
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  color: var(--danger);
}

.icon-btn svg {
  width: 14px;
  height: 14px;
}
</style>
