import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'
import ConfigView from './views/ConfigView.vue'
import LiveView from './views/LiveView.vue'
import LoginView from './views/LoginView.vue'
import ReportsView from './views/ReportsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/live' },
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/live', component: LiveView },
    { path: '/reports', component: ReportsView },
    { path: '/config', component: ConfigView },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.checked) await auth.check()
  if (!to.meta.public && !auth.user) return '/login'
  if (to.path === '/login' && auth.user) return '/live'
  return true
})
