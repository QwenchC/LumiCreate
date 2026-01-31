import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/views/ProjectList.vue'),
        meta: { title: '项目列表' }
      },
      {
        path: 'project/:id',
        name: 'project',
        component: () => import('@/views/ProjectEditor.vue'),
        meta: { title: '项目编辑' }
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: () => import('@/views/TaskCenter.vue'),
        meta: { title: '任务中心' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'LumiCreate'} - 智能说书人`
  next()
})

export default router
