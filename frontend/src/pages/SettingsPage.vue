<script setup>
import { onMounted, ref } from 'vue'
import { getOllamaStatus } from '../lib/api'
import ToastHost from '../components/ToastHost.vue'

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const loading = ref(false)
const toast = ref(null)
const status = ref(null)

const setToast = (text) => {
  toast.value = { text }
  setTimeout(() => {
    toast.value = null
  }, 2200)
}

const refresh = async (silent = false) => {
  loading.value = true
  try {
    status.value = await getOllamaStatus()
    if (!silent) setToast('已刷新')
  } catch (e) {
    setToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => refresh(true))
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="grid">
    <section class="card">
      <div class="card-hd">
        <h2 class="title">接口</h2>
        <button class="btn" :disabled="loading" @click="refresh(false)">{{ loading ? '刷新中…' : '刷新' }}</button>
      </div>
      <div class="card-bd">
        <div class="muted" style="font-size: 12px">前端通过 VITE_API_BASE_URL 指向后端</div>
        <div style="margin-top: 10px; font-weight: 650">{{ apiBase }}</div>
      </div>
    </section>

    <section class="card">
      <div class="card-hd">
        <h2 class="title">Ollama 状态</h2>
        <div class="muted" style="font-size: 12px">后端接口：/api/qa/ollama/status/</div>
      </div>
      <div class="card-bd" v-if="status">
        <div class="row" style="justify-content: space-between">
          <div class="row">
            <span class="tag" :class="status.ok ? 'tag-success' : 'tag-danger'">{{ status.ok ? '可用' : '不可用' }}</span>
            <span class="tag" :class="status.model_available ? 'tag-success' : 'tag-warn'">
              {{ status.model_available ? '模型可用' : '模型未匹配' }}
            </span>
          </div>
          <div class="muted" style="font-size: 12px">{{ status.base_url }}</div>
        </div>

        <div style="margin-top: 12px">
          <div class="muted" style="font-size: 12px">当前模型</div>
          <div style="margin-top: 6px; font-weight: 650">{{ status.model }}</div>
        </div>

        <div style="margin-top: 14px">
          <div class="muted" style="font-size: 12px">可用模型</div>
          <div class="models" v-if="status.available_models && status.available_models.length">
            <span class="tag" v-for="m in status.available_models" :key="m">{{ m }}</span>
          </div>
          <div v-else class="muted" style="margin-top: 8px">列表为空，可能未拉取任何模型。</div>
        </div>

        <div v-if="status.error" style="margin-top: 12px; color: var(--danger); font-size: 12px; white-space: pre-wrap">
          {{ status.error }}
        </div>
      </div>
      <div class="card-bd muted" v-else>加载中…</div>
    </section>

    <section class="card">
      <div class="card-hd">
        <h2 class="title">排障提示</h2>
      </div>
      <div class="card-bd">
        <div class="muted" style="font-size: 12px; line-height: 1.7">
          若问答接口返回“模型未找到”，请以“可用模型”列表为准更新后端 .env 的 OLLAMA_MODEL，然后重启后端服务。
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

.models {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
</style>
