<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const items = [
  { to: '/documents', label: '文档' },
  { to: '/qa', label: '问答' },
  { to: '/graph', label: '图谱' },
  { to: '/tasks', label: '任务' }
]
</script>

<template>
  <nav class="btm">
    <router-link v-for="it in items" :key="it.to" class="btm-item" :class="{ active: route.path === it.to }" :to="it.to">
      <div class="btm-label">{{ it.label }}</div>
    </router-link>
  </nav>
</template>

<style scoped>
.btm {
  display: none;
}

@media (max-width: 768px) {
  .btm {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: 64px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    background: rgba(245, 246, 248, 0.86);
    backdrop-filter: blur(10px);
  }

  .btm-item {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    border: 1px solid transparent;
    color: var(--muted);
  }

  .btm-item.active {
    color: var(--text);
    border-color: rgba(47, 111, 235, 0.24);
    background: rgba(47, 111, 235, 0.08);
  }

  .btm-label {
    font-size: 12px;
    font-weight: 600;
  }
}
</style>
