import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../pages/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/force-change-password',
    name: 'ForceChangePassword',
    component: () => import('../pages/force-change-password/index.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('../layout/index.vue'),
    redirect: '/downloads',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'downloads',
        name: 'Downloads',
        component: () => import('../pages/downloads/index.vue'),
        meta: { title: '下载任务', requiresAuth: true }
      },
      {
        path: 'completed',
        name: 'Completed',
        component: () => import('../pages/completed/index.vue'),
        meta: { title: '已下载任务', requiresAuth: true }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../pages/settings/index.vue'),
        meta: { title: '任务设置', requiresAuth: true }
      },
      {
        path: 'files',
        name: 'Files',
        component: () => import('../pages/files/index.vue'),
        meta: { title: '文件管理', requiresAuth: true }
      },
      {
        path: 'share',
        name: 'Share',
        component: () => import('../pages/share/index.vue'),
        meta: { title: '共享设置', requiresAuth: true }
      },
      {
        path: 'change-password',
        name: 'ChangePassword',
        component: () => import('../pages/change-password/index.vue'),
        meta: { title: '修改密码', requiresAuth: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

export function setupRouterGuards(router) {
  router.beforeEach(async (to, from, next) => {
    const auth = useAuthStore()

    // Listen for session expiration
    window.removeEventListener('session-expired', handleSessionExpired)
    window.addEventListener('session-expired', handleSessionExpired)

    // Skip auth for certain routes
    if (to.path === '/login' || to.path === '/force-change-password') {
      // If not authenticated but has token, validate it first
      if (!auth.isAuthenticated && auth.hasToken()) {
        const isValid = await auth.validateToken()
        if (isValid && !auth.mustChangePassword) {
          next('/')
          return
        }
        if (isValid && auth.mustChangePassword) {
          next('/force-change-password')
          return
        }
      }
      // If already authenticated and visiting login, go to home
      if (to.path === '/login' && auth.isAuthenticated && !auth.mustChangePassword) {
        next('/')
        return
      }
      next()
      return
    }

    // Check if route requires auth
    if (to.meta.requiresAuth !== false) {
      // If must change password, redirect to force change password page
      if (auth.mustChangePassword) {
        next('/force-change-password')
        return
      }

      // Validate existing token if not authenticated
      if (!auth.isAuthenticated && auth.hasToken()) {
        const isValid = await auth.validateToken()
        if (!isValid) {
          next('/login')
          return
        }
        // Check again after validation
        if (auth.mustChangePassword) {
          next('/force-change-password')
          return
        }
      }

      if (!auth.isAuthenticated) {
        next('/login')
        return
      }
    }

    next()
  })
}

function handleSessionExpired() {
  const auth = useAuthStore()
  auth.logout()
  // Redirect to login page
  window.location.href = '/login'
}

export default routes
