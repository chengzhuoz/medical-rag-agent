<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const items = [
  { to: '/documents', label: '文档' },
  { to: '/qa', label: '问答' },
  { to: '/graph', label: '图谱' },
  { to: '/tasks', label: '任务' },
  { to: '/settings', label: '设置' }
]
</script>

<template>
  <nav class="nav">
    <router-link v-for="it in items" :key="it.to" class="nav-item" :class="{ active: route.path === it.to }" :to="it.to">
      {{ it.label }}
    </router-link>
  </nav>
</template>

<style scoped>
.nav {
  display: grid;
  gap: 8px;
}

.nav-item {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  color: var(--muted);
  background: rgba(16, 19, 26, 0.01);
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
}

.nav-item:hover {
  color: var(--text);
  border-color: rgba(16, 19, 26, 0.12);
  background: rgba(16, 19, 26, 0.03);
}

.nav-item.active {
  color: var(--text);
  border-color: rgba(47, 111, 235, 0.24);
  background: rgba(47, 111, 235, 0.08);
}
</style>
