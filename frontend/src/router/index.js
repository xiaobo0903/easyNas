import { createRouter, createWebHistory } from 'vue-router'
import routes, { setupRouterGuards } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes
})

setupRouterGuards(router)

export default router
