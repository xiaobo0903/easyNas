import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref(false)
  const mustChangePassword = ref(false)
  const loading = ref(false)

  const isFirstLogin = computed(() => {
    return mustChangePassword.value
  })

  // Check if there's a valid JWT token in localStorage
  const hasToken = () => !!localStorage.getItem('easynas_token')

  // Get token expiration time from JWT payload
  function getTokenExpiration() {
    const token = localStorage.getItem('easynas_token')
    if (!token) return null
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.exp ? payload.exp * 1000 : null // Convert to milliseconds
    } catch (e) {
      return null
    }
  }

  // Check if token is expired
  function isTokenExpired() {
    const expTime = getTokenExpiration()
    if (!expTime) return true
    return Date.now() >= expTime
  }

  async function validateToken() {
    if (!hasToken()) return false
    if (isTokenExpired()) {
      localStorage.removeItem('easynas_token')
      return false
    }
    try {
      const res = await authAPI.status()
      if (res.data.authenticated !== false) {
        isAuthenticated.value = true
        mustChangePassword.value = res.data.mustChangePassword || false
        return true
      }
    } catch (e) {
      // Token invalid or expired
    }
    localStorage.removeItem('easynas_token')
    return false
  }

  async function login(password) {
    loading.value = true
    try {
      const res = await authAPI.login(password)
      if (res.data.success) {
        isAuthenticated.value = true
        mustChangePassword.value = res.data.user?.mustChangePassword || false
        // Store JWT token
        if (res.data.token) {
          localStorage.setItem('easynas_token', res.data.token)
        }
        return { success: true, mustChangePassword: mustChangePassword.value }
      }
      return { success: false, error: res.data.error }
    } catch (e) {
      return { success: false, error: e.response?.data?.error || '登录失败' }
    } finally {
      loading.value = false
    }
  }

  async function changePassword(oldPassword, newPassword) {
    loading.value = true
    try {
      const res = await authAPI.changePassword(oldPassword, newPassword)
      if (res.data.success) {
        mustChangePassword.value = false
        return { success: true }
      }
      return { success: false, error: res.data.error }
    } catch (e) {
      return { success: false, error: e.response?.data?.error || '修改失败' }
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await authAPI.logout()
    } catch (e) {
      // Ignore logout errors
    }
    isAuthenticated.value = false
    localStorage.removeItem('easynas_token')
  }

  return {
    isAuthenticated,
    mustChangePassword,
    loading,
    isFirstLogin,
    hasToken,
    isTokenExpired,
    validateToken,
    login,
    changePassword,
    logout,
  }
})