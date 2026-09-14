<script setup>
import { computed, onMounted, ref } from 'vue'
import { askQuestion, getOllamaStatus, listDocuments } from '../lib/api'
import { docStatusLabel, statusTagClass } from '../lib/format'
import ToastHost from '../components/ToastHost.vue'
import { useRouter } from 'vue-router'

const docs = ref([])
const selected = ref({})
const question = ref('')
const topK = ref(4)
const asking = ref(false)
const refreshingDocs = ref(false)
const refreshingOllama = ref(false)
const result = ref(null)
const toast = ref(null)
const ollama = ref(null)
const router = useRouter()

const setToast = (text) => {
  toast.value = { text }
  setTimeout(() => {
    toast.value = null
  }, 2200)
}

const selectedIds = computed(() => Object.keys(selected.value).filter((k) => selected.value[k]))
const selectedCount = computed(() => selectedIds.value.length)
const busy = computed(() => asking.value || refreshingDocs.value || refreshingOllama.value)

const refreshDocs = async (silent = false) => {
  refreshingDocs.value = true
  try {
    docs.value = await listDocuments()
    if (!silent) setToast('文档已刷新')
  } catch (e) {
    setToast(e.message || '加载文档失败')
  } finally {
    refreshingDocs.value = false
  }
}

const refreshOllama = async (silent = false) => {
  refreshingOllama.value = true
  try {
    ollama.value = await getOllamaStatus()
    if (!silent) setToast('状态已刷新')
  } catch (e) {
    ollama.value = { ok: false, error: e.message || '无法连接 Ollama' }
  } finally {
    refreshingOllama.value = false
  }
}

const onAsk = async () => {
  if (!question.value.trim()) return
  asking.value = true
  result.value = null
  try {
    const r = await askQuestion({ question: question.value.trim(), document_ids: selectedIds.value, top_k: topK.value })
    result.value = r
  } catch (e) {
    setToast(e.message || '问答失败')
  } finally {
    asking.value = false
  }
}

onMounted(async () => {
  await refreshDocs(true)
  await refreshOllama(true)
})

const openGraph = (center) => {
  if (!center) return
  router.push({ path: '/graph', query: { center } })
}
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="grid">
    <section class="card">
      <div class="card-hd">
        <h2 class="title">提问</h2>
        <div class="muted" style="font-size: 12px" v-if="ollama">
          Ollama：{{ ollama.ok ? '可用' : '不可用' }} / 模型：{{ ollama.model || '-' }}
        </div>
      </div>
      <div class="card-bd">
        <textarea class="field" rows="4" v-model="question" placeholder="请输入问题，例如：糖尿病肾病的一线治疗方案有哪些？" />
        <div class="row" style="margin-top: 12px; justify-content: space-between">
          <div class="row">
            <label class="muted" style="font-size: 12px">TopK</label>
            <input class="field" type="number" min="1" max="20" style="width: 90px" v-model.number="topK" />
          </div>
          <div class="row">
            <button class="btn" :disabled="busy" @click="refreshDocs(false)">
              <span v-if="refreshingDocs" class="spinner" />
              {{ refreshingDocs ? '刷新中…' : '刷新文档' }}
            </button>
            <button class="btn btn-primary" :disabled="busy" @click="onAsk">
              <span v-if="asking" class="spinner" />
              {{ asking ? '生成中…' : '问答' }}
            </button>
          </div>
        </div>
        <div v-if="asking" class="muted" style="margin-top: 10px; font-size: 12px">正在生成回答中…</div>
        <div v-if="ollama && ollama.ok && !ollama.model_available" class="muted" style="margin-top: 10px; font-size: 12px; color: var(--warn)">
          当前配置的模型不在 Ollama 列表中，请在“设置”页检查可用模型名称，并更新后端 OLLAMA_MODEL。
        </div>
      </div>
    </section>

    <section class="card" v-if="asking || result">
      <div class="card-hd">
        <h2 class="title">回答</h2>
        <div class="muted" style="font-size: 12px">建议阅读证据片段核对来源</div>
      </div>
      <div class="card-bd">
        <div v-if="asking" class="loading-row">
          <span class="spinner" />
          <div class="muted" style="font-size: 13px">正在生成回答中…</div>
        </div>
        <pre v-else class="answer">{{ result.answer }}</pre>
      </div>
    </section>

    <section class="card" v-if="result">
      <div class="card-hd">
        <h2 class="title">证据片段</h2>
        <div class="muted" style="font-size: 12px">Top {{ result.contexts?.length || 0 }}</div>
      </div>
      <div class="card-bd">
        <div v-if="result.contexts && result.contexts.length" class="ctx-grid">
          <div class="ctx" v-for="c in result.contexts" :key="c.rank">
            <div class="muted" style="font-size: 12px; margin-bottom: 8px">[{{ c.rank }}] {{ c.metadata?.original_name || '' }}</div>
            <div class="ctx-text">{{ c.text }}</div>
          </div>
        </div>
        <div v-else class="muted">未检索到证据片段，请先对文档完成解析与向量化。</div>
      </div>
    </section>

    <section class="card" v-if="result && result.graph">
      <div class="card-hd">
        <h2 class="title">图谱线索</h2>
        <div class="muted" style="font-size: 12px">来自 Neo4j 的实体与关系</div>
      </div>
      <div class="card-bd">
        <div v-if="result.graph.keywords && result.graph.keywords.length" class="row">
          <span class="muted" style="font-size: 12px">关键词</span>
          <button class="btn" v-for="k in result.graph.keywords" :key="k" @click="openGraph(k)">{{ k }}</button>
        </div>
        <div class="muted" style="margin-top: 10px" v-else>暂无图谱线索（可能未配置 Neo4j 或未构建图谱）。</div>
      </div>
    </section>

    <section class="card">
      <div class="card-hd">
        <h2 class="title">限定文档（可选）</h2>
        <div class="muted" style="font-size: 12px">
          不选则在全部向量中检索 · 已选 {{ selectedCount }} / {{ docs.length }}
        </div>
      </div>
      <div class="card-bd">
        <div v-if="docs.length" class="doc-grid">
          <label v-for="d in docs" :key="d.id" class="doc-item">
            <input type="checkbox" v-model="selected[d.id]" />
            <div class="doc-meta">
              <div class="doc-name">{{ d.original_name }}</div>
              <div class="row" style="margin-top: 6px">
                <span :class="statusTagClass(d.status)">{{ docStatusLabel(d.status) }}</span>
              </div>
            </div>
          </label>
        </div>
        <div v-else-if="refreshingDocs" class="loading-row">
          <span class="spinner" />
          <div class="muted">加载文档中…</div>
        </div>
        <div v-else class="muted">暂无文档。</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  gap: 16px;
}

.loading-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.spinner {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid rgba(16, 19, 26, 0.14);
  border-top-color: rgba(16, 19, 26, 0.5);
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.doc-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.doc-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
}

.doc-name {
  font-size: 13px;
  font-weight: 650;
}

.answer {
  white-space: pre-wrap;
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
}

.ctx-grid {
  display: grid;
  gap: 10px;
}

.ctx {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.ctx-text {
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 768px) {
  .doc-grid {
    grid-template-columns: 1fr;
  }
}
</style>
