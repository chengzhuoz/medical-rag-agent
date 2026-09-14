<script setup>
import { onMounted, ref } from 'vue'
import { getTask, listTasks } from '../lib/api'
import { formatTime, statusTagClass, taskStatusLabel } from '../lib/format'
import ToastHost from '../components/ToastHost.vue'

const tasks = ref([])
const loading = ref(false)
const selected = ref(null)
const toast = ref(null)

const setToast = (text) => {
  toast.value = { text }
  setTimeout(() => {
    toast.value = null
  }, 2200)
}

const refresh = async (silent = false) => {
  loading.value = true
  try {
    tasks.value = await listTasks()
    if (!silent) setToast('已刷新')
  } catch (e) {
    setToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const open = async (id) => {
  loading.value = true
  try {
    selected.value = await getTask(id)
  } catch (e) {
    setToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const close = () => {
  selected.value = null
}

onMounted(() => refresh(true))
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="grid">
    <section class="card">
      <div class="card-hd">
        <h2 class="title">任务</h2>
        <div class="row">
          <button class="btn" :disabled="loading" @click="refresh(false)">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
      </div>
      <div class="card-bd" style="padding: 0">
        <table class="table" v-if="tasks.length">
          <thead>
            <tr>
              <th style="width: 16%">类型</th>
              <th style="width: 18%">状态</th>
              <th style="width: 22%">文档</th>
              <th style="width: 22%">开始</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id">
              <td style="font-weight: 650">{{ t.task_type }}</td>
              <td><span :class="statusTagClass(t.status)">{{ taskStatusLabel(t.status) }}</span></td>
              <td class="muted" style="font-size: 12px">{{ t.document_id || '-' }}</td>
              <td class="muted" style="font-size: 12px">{{ formatTime(t.created_at) }}</td>
              <td>
                <button class="btn" :disabled="loading" @click="open(t.id)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="card-bd muted">暂无任务记录。</div>
      </div>
    </section>

    <section v-if="selected" class="drawer" @click.self="close">
      <div class="drawer-body card">
        <div class="card-hd">
          <h2 class="title">任务详情</h2>
          <button class="btn" @click="close">关闭</button>
        </div>
        <div class="card-bd">
          <div class="row" style="justify-content: space-between">
            <div class="row">
              <span class="tag">{{ selected.task_type }}</span>
              <span :class="statusTagClass(selected.status)">{{ taskStatusLabel(selected.status) }}</span>
            </div>
            <div class="muted" style="font-size: 12px">{{ formatTime(selected.created_at) }}</div>
          </div>

          <div v-if="selected.error" style="margin-top: 12px; color: var(--danger); font-size: 12px; white-space: pre-wrap">
            {{ selected.error }}
          </div>

          <div style="margin-top: 14px; font-size: 13px; font-weight: 650">日志</div>
          <div v-if="selected.logs && selected.logs.length" class="logs">
            <div v-for="l in selected.logs" :key="l.id" class="log">
              <div class="muted" style="font-size: 12px; width: 120px">{{ formatTime(l.created_at) }}</div>
              <div class="log-msg" :class="{ err: l.level === 'error' }">{{ l.message }}</div>
            </div>
          </div>
          <div v-else class="muted" style="margin-top: 10px">无日志。</div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  gap: 16px;
}

.drawer {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  justify-content: flex-end;
  z-index: 10;
}

.drawer-body {
  width: min(560px, 100%);
  height: 100%;
  border-radius: 0;
  border-left: 1px solid var(--border);
  overflow: auto;
}

.logs {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.log {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
}

.log-msg {
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.log-msg.err {
  color: var(--danger);
}

@media (max-width: 768px) {
  .drawer-body {
    width: 100%;
  }
}
</style>
