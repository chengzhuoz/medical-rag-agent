import { createRouter, createWebHistory } from 'vue-router'

import DocumentsPage from './pages/DocumentsPage.vue'
import QaPage from './pages/QaPage.vue'
import TasksPage from './pages/TasksPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import GraphPage from './pages/GraphPage.vue'
import ObservabilityPage from './pages/ObservabilityPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/documents' },
    { path: '/documents', component: DocumentsPage },
    { path: '/qa', component: QaPage },
    { path: '/graph', component: GraphPage },
    { path: '/tasks', component: TasksPage },
    { path: '/observability', component: ObservabilityPage },
    { path: '/settings', component: SettingsPage }
  ]
})

export default router