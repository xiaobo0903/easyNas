import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8080/api',
  timeout: 30000,
})

// Add token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('easynas_token')
  if (token) {
    config.headers['X-Session-Token'] = token
  }
  return config
})

// Handle session expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const code = error.response?.data?.code
      // Skip session expired handling for logout endpoint (401 is expected if session already invalid)
      if (code === 'SESSION_EXPIRED' && !error.config?.url?.includes('/auth/logout')) {
        localStorage.removeItem('easynas_token')
        localStorage.removeItem('easynas_password')
        // Dispatch event to notify app to logout
        window.dispatchEvent(new CustomEvent('session-expired'))
      }
    }
    return Promise.reject(error)
  }
)

export const taskAPI = {
  list: () => api.get('/tasks'),
  get: (id) => api.get(`/tasks/${id}`),
  add: (data) => api.post('/tasks', data),
  pause: (id) => api.post(`/tasks/${id}/pause`),
  resume: (id) => api.post(`/tasks/${id}/resume`),
  remove: (id, deleteFiles = false) => api.delete(`/tasks/${id}?deleteFiles=${deleteFiles}`),
  pauseAll: () => api.post('/tasks/pause-all'),
  resumeAll: () => api.post('/tasks/resume-all'),
  clearCompleted: () => api.post('/tasks/clear-completed'),
}

export const fileAPI = {
  list: (path = '', sort = 'name') => api.get(`/files?path=${encodeURIComponent(path)}&sort=${sort}`),
  mkdir: (path, name) => api.post('/files/mkdir', { path, name }),
  rename: (path, newName) => api.post('/files/rename', { path, newName }),
  delete: (paths) => api.post('/files/delete', { paths }),
  move: (paths, targetPath) => api.post('/files/move', { paths, targetPath }),
  copy: (paths, targetPath = '') => api.post('/files/copy', { paths, targetPath }),
  download: (path) => api.get(`/files/download?path=${encodeURIComponent(path)}`),
}

export const settingsAPI = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
}

export const statsAPI = {
  get: () => api.get('/stats'),
}

export const healthAPI = {
  check: () => api.get('/health'),
}

export const shareAPI = {
  getStatus: () => api.get('/share/status'),
  enable: () => api.post('/share/enable'),
  disable: () => api.post('/share/disable'),
}

export const authAPI = {
  login: (password) => api.post('/auth/login', { password }),
  status: () => api.get('/auth/status'),
  changePassword: (oldPassword, newPassword) => api.post('/auth/change-password', { oldPassword, newPassword }),
  logout: () => api.post('/auth/logout'),
}

export default api
