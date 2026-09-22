<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { getObservabilityOverview, listTasks } from '../lib/api'

const overview = ref(null)
const tasks = ref([])
const loading = ref(true)
const error = ref('')
let timer = null

const refresh = async () => {
  try {
    const [overviewData, taskData] = await Promise.all([getObservabilityOverview(), listTasks()])
    overview.value = overviewData
    tasks.value = taskData.slice(0, 8)
    error.value = ''
  } catch (requestError) {
    error.value = requestError.message || '监控数据加载失败'
  } finally {
    loading.value = false
  }
}

const open = (url) => {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => { refresh(); timer = window.setInterval(refresh, 15000) })
onUnmounted(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="observability-page">
    <header class="page-header">
      <div><span class="eyebrow">OBSERVABILITY CENTER</span><h1>系统可观测性</h1><p>集中查看 Agent 链路追踪、运行指标与任务状态，数据每 15 秒刷新。</p></div>
      <button class="btn btn-primary" :disabled="loading" @click="refresh">{{ loading ? '加载中…' : '刷新数据' }}</button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <template v-else-if="overview">
      <section class="system-grid">
        <article class="system-card"><div class="system-icon langsmith">⌁</div><div><span>LangSmith Trace</span><strong>{{ overview.langsmith.enabled ? '已启用' : '未配置' }}</strong><small>项目：{{ overview.langsmith.project }}</small></div><button class="open-btn" :disabled="!overview.langsmith.dashboard_url" @click="open(overview.langsmith.dashboard_url)">打开 ↗</button></article>
        <article class="system-card"><div class="system-icon prometheus">▥</div><div><span>Prometheus Metrics</span><strong>采集中</strong><small>后端指标：{{ overview.prometheus.metrics_url }}</small></div><button class="open-btn" @click="open(overview.prometheus.dashboard_url)">打开 ↗</button></article>
        <article class="system-card"><div class="system-icon grafana">◌</div><div><span>Grafana Dashboard</span><strong>看板已就绪</strong><small>自动载入 Medical RAG Overview</small></div><button class="open-btn" @click="open(overview.grafana.dashboard_url)">打开 ↗</button></article>
      </section>

      <section class="metrics-grid"><article><span>运行任务</span><b>{{ overview.tasks.running }}</b><small>当前进行中</small></article><article><span>成功任务</span><b class="success">{{ overview.tasks.succeeded }}</b><small>累计完成</small></article><article><span>失败任务</span><b :class="{ danger: overview.tasks.failed }">{{ overview.tasks.failed }}</b><small>需要排查</small></article><article><span>采集周期</span><b>15s</b><small>Prometheus scrape</small></article></section>

      <section class="detail-card"><div class="detail-header"><div><h2>监控信号</h2><p>运行一次问答后，可在 Prometheus 和 Grafana 中观察以下指标。</p></div><a :href="overview.prometheus.metrics_url" target="_blank">查看原始 /metrics ↗</a></div><div class="signal-grid"><div><b>HTTP</b><span>请求量、延迟、并发、5xx</span><code>medical_rag_http_*</code></div><div><b>多 Agent</b><span>Router / Retriever / Answer / Reviewer 耗时</span><code>medical_rag_agent_duration_seconds</code></div><div><b>工具</b><span>Milvus、Neo4j、规则、联网搜索调用结果</span><code>medical_rag_tool_*</code></div><div><b>重排序</b><span>Cross-Encoder 成功、失败与候选数量</span><code>medical_rag_rerank_*</code></div></div></section>

      <section class="detail-card"><div class="detail-header"><div><h2>近期任务</h2><p>来自项目内置任务日志，可与 Grafana 时间范围对照排查。</p></div></div><div class="task-table"><div class="task-row task-head"><span>类型</span><span>状态</span><span>开始时间</span><span>错误信息</span></div><div v-for="task in tasks" :key="task.id" class="task-row"><span>{{ task.task_type }}</span><span :class="['status', task.status]">{{ task.status }}</span><span>{{ task.created_at?.replace('T', ' ').slice(0, 19) }}</span><span>{{ task.error || '-' }}</span></div><div v-if="!tasks.length" class="no-tasks">暂无任务记录</div></div></section>
    </template>
  </div>
</template>

<style scoped>
.observability-page{max-width:1180px;margin:0 auto}.page-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}.eyebrow{display:block;font-size:10px;letter-spacing:.16em;font-weight:800;color:#4978d3}.page-header h1{font-size:28px;letter-spacing:-.04em;margin:7px 0 4px}.page-header p{margin:0;color:var(--muted);font-size:13px}.system-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:15px}.system-card{background:#fff;border:1px solid var(--border);border-radius:15px;padding:17px;display:flex;align-items:center;gap:11px;box-shadow:var(--shadow)}.system-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:11px;font-size:19px}.langsmith{color:#805ad5;background:#f1ebff}.prometheus{color:#d55a2a;background:#fff0e9}.grafana{color:#e58a1f;background:#fff6e7}.system-card div:nth-child(2){min-width:0;flex:1}.system-card span,.system-card strong,.system-card small{display:block}.system-card span{font-size:11px;color:var(--muted)}.system-card strong{font-size:14px;margin:2px 0}.system-card small{font-size:10px;color:#8a96a8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.open-btn{border:0;background:transparent;color:#4072ca;font-size:11px;cursor:pointer}.open-btn:disabled{color:#aab4c3;cursor:not-allowed}.metrics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:15px}.metrics-grid article{background:#fff;border:1px solid var(--border);border-radius:14px;padding:17px}.metrics-grid span,.metrics-grid b,.metrics-grid small{display:block}.metrics-grid span{font-size:11px;color:var(--muted)}.metrics-grid b{font-size:27px;margin:4px 0;color:#253753}.metrics-grid small{font-size:10px;color:#9aa5b4}.metrics-grid .success{color:#14885f}.metrics-grid .danger{color:#c64242}.detail-card{background:#fff;border:1px solid var(--border);border-radius:15px;margin-bottom:15px;overflow:hidden}.detail-header{padding:18px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}.detail-header h2{font-size:15px;margin:0}.detail-header p{margin:4px 0 0;font-size:11px;color:var(--muted)}.detail-header a{font-size:11px;color:#4072ca}.signal-grid{display:grid;grid-template-columns:repeat(4,1fr)}.signal-grid div{padding:17px;border-right:1px solid var(--border)}.signal-grid div:last-child{border-right:0}.signal-grid b,.signal-grid span{display:block}.signal-grid b{font-size:12px}.signal-grid span{font-size:11px;color:var(--muted);min-height:34px;margin:4px 0}.signal-grid code{font-size:9px;color:#6b7d99;background:#f2f5f9;padding:3px 5px;border-radius:4px}.task-table{font-size:11px}.task-row{display:grid;grid-template-columns:100px 100px 190px 1fr;gap:12px;padding:12px 20px;border-bottom:1px solid var(--border)}.task-row:last-child{border-bottom:0}.task-head{font-weight:700;color:var(--muted);background:#fafbfc}.status{font-weight:700}.status.succeeded{color:#14885f}.status.failed{color:#c64242}.status.running{color:#b8781c}.no-tasks{padding:22px;color:var(--muted);text-align:center}.alert{padding:12px 15px;background:#fff1f0;border:1px solid #ffd3cf;color:#b33e38;border-radius:10px;margin-bottom:16px;font-size:12px}@media(max-width:900px){.system-grid,.metrics-grid{grid-template-columns:1fr 1fr}.signal-grid{grid-template-columns:1fr 1fr}.signal-grid div:nth-child(2){border-right:0}.task-row{grid-template-columns:80px 80px 1fr}.task-row span:last-child{display:none}}@media(max-width:600px){.page-header{gap:13px;flex-direction:column}.system-grid,.metrics-grid,.signal-grid{grid-template-columns:1fr}.signal-grid div{border-right:0;border-bottom:1px solid var(--border)}.task-row{grid-template-columns:1fr 1fr}.task-row span:nth-child(3){display:none}}
</style>