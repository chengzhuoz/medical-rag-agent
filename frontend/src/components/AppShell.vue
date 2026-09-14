<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import SidebarNav from './SidebarNav.vue'
import BottomNav from './BottomNav.vue'

const route = useRoute()
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const title = computed(() => {
  const m = {
    '/documents': '文档',
    '/qa': '问答',
    '/graph': '图谱',
    '/tasks': '任务',
    '/settings': '设置'
  }
  return m[route.path] || '公共卫生知识助手'
})
</script>

<template>
  <div class="app">
    <aside class="side">
      <div class="brand">
        <div class="brand-title">公共卫生</div>
        <div class="brand-sub muted">知识图谱与检索问答</div>
      </div>
      <SidebarNav />
      <div class="side-ft muted">API：{{ apiBase }}</div>
    </aside>

    <div class="main">
      <header class="top">
        <div class="container top-in">
          <div class="top-title">{{ title }}</div>
        </div>
      </header>

      <main class="content">
        <div class="container">
          <router-view />
        </div>
      </main>

      <BottomNav />
    </div>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px 1fr;
}

.side {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 18px 14px;
  border-right: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand {
  padding: 10px 10px 12px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(16, 19, 26, 0.02);
}

.brand-title {
  font-weight: 700;
  letter-spacing: 0.2px;
}

.brand-sub {
  font-size: 12px;
  margin-top: 4px;
}

.side-ft {
  margin-top: auto;
  font-size: 12px;
  padding: 0 8px;
  opacity: 0.85;
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.top {
  position: sticky;
  top: 0;
  z-index: 2;
  border-bottom: 1px solid var(--border);
  background: rgba(245, 246, 248, 0.75);
  backdrop-filter: blur(10px);
}

.top-in {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.top-title {
  font-size: 14px;
  font-weight: 650;
}

.content {
  padding: 22px 0 80px;
}

@media (max-width: 768px) {
  .app {
    grid-template-columns: 1fr;
  }
  .side {
    display: none;
  }
  .content {
    padding-bottom: 92px;
  }
}
</style>
