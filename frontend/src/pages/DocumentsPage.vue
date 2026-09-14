<script setup>
import { onMounted, ref } from 'vue'
import { ApiError, buildKgForDocument, embedDocument, getDocument, listDocuments, parseDocument, uploadDocument } from '../lib/api'
import { docStatusLabel, formatTime, statusTagClass } from '../lib/format'
import ToastHost from '../components/ToastHost.vue'

const docs = ref([])
const loading = ref(false)
const fileRef = ref(null)
const toast = ref(null)
const detail = ref(null)

const setToast = (text) => {
  toast.value = { text }
  setTimeout(() => {
    toast.value = null
  }, 2200)
}

const refresh = async (silent = false) => {
  loading.value = true
  try {
    docs.value = await listDocuments()
    if (!silent) setToast('已刷新')
  } catch (e) {
    setToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const onUpload = async () => {
  const el = fileRef.value
  const f = el && el.files && el.files[0]
  if (!f) return
  loading.value = true
  try {
    await uploadDocument(f)
    el.value = ''
    setToast('上传成功')
    await refresh(true)
  } catch (e) {
    setToast(e.message || '上传失败')
  } finally {
    loading.value = false
  }
}

const onParse = async (id) => {
  loading.value = true
  try {
    const r = await parseDocument(id)
    setToast(`解析完成（pages=${r.pages} chunks=${r.chunks}）`)
    await refresh(true)
  } catch (e) {
    setToast(e.message || '解析失败')
  } finally {
    loading.value = false
  }
}

const onEmbed = async (id) => {
  loading.value = true
  try {
    await embedDocument(id)
    setToast('向量化完成')
    await refresh(true)
  } catch (e) {
    setToast(e.message || '向量化失败')
  } finally {
    loading.value = false
  }
}

const onBuildKg = async (id) => {
  loading.value = true
  try {
    const r = await buildKgForDocument(id)
    if (r && r.ok === false) {
      setToast(r.error || '图谱构建失败（Neo4j 未配置或不可用）')
    } else {
      setToast('图谱构建完成')
    }
  } catch (e) {
    setToast(e.message || '图谱构建失败')
  } finally {
    loading.value = false
  }
}


const onView = async (id) => {
  loading.value = true
  try {
    detail.value = await getDocument(id)
  } catch (e) {
    setToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const closeDetail = () => {
  detail.value = null
}

onMounted(() => refresh(true))
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="grid">
    <section class="card">
      <div class="card-hd">
        <h2 class="title">上传 PDF</h2>
        <div class="muted" style="font-size: 12px">支持诊疗规范/政策文件等</div>
      </div>
      <div class="card-bd">
        <div class="row">
          <input ref="fileRef" class="field" type="file" accept="application/pdf" style="max-width: 520px" />
          <button class="btn btn-primary" :disabled="loading" @click="onUpload">上传</button>
          <button class="btn" :disabled="loading" @click="refresh(false)">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
        <div class="muted" style="margin-top: 10px; font-size: 12px">上传后依次执行：解析 → 向量化 → 问答</div>
      </div>
    </section>

    <section class="card">
      <div class="card-hd">
        <h2 class="title">文档列表</h2>
        <div class="muted" style="font-size: 12px">{{ loading ? '处理中…' : `共 ${docs.length} 份` }}</div>
      </div>
      <div class="card-bd" style="padding: 0">
        <table class="table" v-if="docs.length">
          <thead>
            <tr>
              <th style="width: 28%">文件名</th>
              <th style="width: 18%">时间</th>
              <th style="width: 12%">状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id">
              <td>
                <div style="font-weight: 650">{{ d.original_name }}</div>
                <div v-if="d.error_message" class="muted" style="font-size: 12px; margin-top: 4px; color: var(--danger)">
                  {{ d.error_message }}
                </div>
              </td>
              <td class="muted" style="font-size: 12px">{{ formatTime(d.uploaded_at) }}</td>
              <td>
                <span :class="statusTagClass(d.status)">{{ docStatusLabel(d.status) }}</span>
              </td>
              <td>
                <div class="row">
                  <button class="btn" :disabled="loading" @click="onView(d.id)">查看</button>
                  <button class="btn" :disabled="loading" @click="onParse(d.id)">解析</button>
                  <button class="btn btn-primary" :disabled="loading" @click="onEmbed(d.id)">向量化</button>
                  <button class="btn" :disabled="loading" @click="onBuildKg(d.id)">构建图谱</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-else class="card-bd muted">暂无文档，请先上传 PDF。</div>
      </div>
    </section>

    <section v-if="detail" class="modal" @click.self="closeDetail">
      <div class="modal-body card">
        <div class="card-hd">
          <h2 class="title">文档内容</h2>
          <div class="row">
            <a v-if="detail.file_url" class="btn" :href="detail.file_url" target="_blank" rel="noreferrer">打开 PDF</a>
            <button class="btn" @click="closeDetail">关闭</button>
          </div>
        </div>
        <div class="card-bd">
          <div class="muted" style="font-size: 12px; margin-bottom: 10px">{{ detail.original_name }}</div>
          <textarea class="field" style="min-height: 320px; resize: vertical" readonly :value="detail.parsed_text || ''" />
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

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  z-index: 10;
}

.modal-body {
  width: min(980px, 100%);
  max-height: calc(100vh - 36px);
  overflow: auto;
}
</style>
