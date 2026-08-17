import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/components/Layout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: Layout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '主控界面' },
        },
        /*
        {
          path: 'monitor',
          name: 'Monitor',
          component: () => import('@/views/Monitor.vue'),
          meta: { title: '参数监控' },
        },
        {
          path: 'history',
          name: 'History',
          component: () => import('@/views/History.vue'),
          meta: { title: '历史数据' },
        },
        */
        {
          path: 'alarm',
          name: 'Alarm',
          component: () => import('@/views/Alarm.vue'),
          meta: { title: '报警管理' },
        },
        /*
        {
          path: 'report',
          name: 'Report',
          component: () => import('@/views/Report.vue'),
          meta: { title: '报表查询' },
        },
        */
      ],
    },
  ],
})

export default router
