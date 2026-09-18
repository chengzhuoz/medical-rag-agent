<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { askQuestion, getOllamaStatus, listDocuments } from '../lib/api'
import { docStatusLabel, statusTagClass } from '../lib/format'
import ToastHost from '../components/ToastHost.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const docs = ref([])
const selected = ref({})
const question = ref('')
const topK = ref(4)
const asking = ref(false)
const loadingDocs = ref(false)
const result = ref(null)
const ollama = ref(null)
const toast = ref(null)
const messages = ref([])
const chatBody = ref(null)
const conversationId = ref(crypto.randomUUID())

// 页面开关会透传到后端 retrieval_options，并由 Retriever 决定实际工具白名单。
const capabilities = ref({ vector: true, graph: true, web: true })
const selectedIds = computed(() => Object.keys(selected.value).filter((id) => selected.value[id]))
const busy = computed(() => asking.value || loadingDocs.value)

const setToast = (text) => {
  toast.value = { text }
  window.setTimeout(() => { toast.value = null }, 2600)
}
const scrollLatest = async () => { await nextTick(); if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight }
const refreshDocs = async () => {
  loadingDocs.value = true
  try { docs.value = await listDocuments() } catch (error) { setToast(error.message || '加载文档失败') } finally { loadingDocs.value = false }
}
const refreshOllama = async () => {
  try { ollama.value = await getOllamaStatus() } catch (error) { ollama.value = { ok: false, error: error.message } }
}
const newConversation = () => { conversationId.value = crypto.randomUUID(); messages.value = []; result.value = null; question.value = '' }
const toggle = (key) => { capabilities.value[key] = !capabilities.value[key] }

const onAsk = async (preset = '') => {
  const text = (preset || question.value).trim()
  if (!text || asking.value) return
  messages.value.push({ role: 'user', content: text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })
  question.value = ''
  result.value = null
  asking.value = true
  await scrollLatest()
  try {
    const response = await askQuestion({
      question: text,
      document_ids: selectedIds.value,
      top_k: topK.value,
      use_vector: capabilities.value.vector,
      use_graph: capabilities.value.graph,
      use_web: capabilities.value.web,
    })
    result.value = response
    messages.value.push({ role: 'assistant', content: response.answer, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })
  } catch (error) {
    messages.value.push({ role: 'error', content: error.message || '服务暂时不可用，请稍后重试。', time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })
    setToast(error.message || '问答失败')
  } finally { asking.value = false; await scrollLatest() }
}
const openGraph = (center) => { if (center) router.push({ path: '/graph', query: { center } }) }
onMounted(() => { refreshDocs(); refreshOllama() })
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="support-page">
    <header class="support-header">
      <div><div class="eyebrow"><span class="live-dot" /> KNOWLEDGE SUPPORT DESK</div><h1>医疗知识问答中心</h1><p>面向医疗器械与公共卫生场景的证据增强式智能客服</p></div>
      <div class="header-actions"><span>会话 {{ conversationId.slice(0, 8) }}</span><button class="btn" :disabled="busy" @click="newConversation">新建会话</button></div>
    </header>
    <div class="workspace">
      <aside class="control-panel">
        <section class="panel-section"><div class="section-heading"><strong>检索能力</strong><span class="tag tag-success">可控</span></div><p class="help">选择本次回答允许使用的数据源。</p>
          <button v-for="item in [{ key: 'vector', icon: '⌁', title: '向量知识库', detail: 'Milvus 语义检索' }, { key: 'graph', icon: '⌘', title: '知识图谱', detail: 'Neo4j 实体关系' }, { key: 'web', icon: '◎', title: '联网搜索', detail: '公开网页时效信息' }]" :key="item.key" class="capability" :class="{ active: capabilities[item.key] }" @click="toggle(item.key)"><span class="cap-icon">{{ item.icon }}</span><span class="cap-copy"><b>{{ item.title }}</b><small>{{ item.detail }}</small></span><i class="switch" /></button>
        </section>
        <section class="panel-section"><div class="section-heading"><strong>会话范围</strong><span class="muted">{{ selectedIds.length }} 个文档</span></div><label class="field-label">召回数量 Top K</label><input class="field compact" type="number" min="1" max="20" v-model.number="topK" /><label class="field-label">限定内部文档</label><div class="doc-list"><label v-for="doc in docs" :key="doc.id" class="doc-row"><input type="checkbox" v-model="selected[doc.id]" /><span class="doc-name">{{ doc.original_name }}</span><span :class="statusTagClass(doc.status)">{{ docStatusLabel(doc.status) }}</span></label><div v-if="loadingDocs || !docs.length" class="empty">{{ loadingDocs ? '正在加载…' : '暂无已上传文档' }}</div></div><button class="text-button" @click="refreshDocs">↻ 刷新文档列表</button></section>
        <section class="panel-section health"><div class="section-heading"><strong>系统状态</strong><span class="tag tag-success">在线</span></div><div>Agent 编排 <b>● MAS</b></div><div>模型服务 <b :class="{ offline: !ollama?.ok }">● {{ ollama?.ok ? 'Ollama' : '检查中' }}</b></div><div>搜索 MCP <b>● Ready</b></div></section>
      </aside>
      <main class="chat-panel">
        <div class="chat-toolbar"><strong>智能客服 <span>· 多源证据问答</span></strong><small>⌁ 结果仅供研究参考</small></div>
        <div ref="chatBody" class="chat-body">
          <div v-if="!messages.length" class="welcome"><div class="welcome-mark">✦</div><h2>您好，我是医疗知识助手</h2><p>我可以结合内部文档、Neo4j、Milvus 与公开网页，帮助您定位依据并整理答案。</p><div class="suggestions"><button @click="onAsk('医疗器械注册需要关注哪些合规要点？')">⌁ 医疗器械注册合规要点</button><button @click="onAsk('请基于当前知识库说明常见风险与特殊人群注意事项。')">◈ 风险与特殊人群提示</button><button @click="onAsk('请搜索最新的公共卫生相关政策，并标注来源。')">◎ 搜索最新公共卫生政策</button></div></div>
          <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role"><div v-if="message.role !== 'user'" class="avatar">✦</div><div class="message-main"><small>{{ message.role === 'user' ? '您' : '医疗知识助手' }} · {{ message.time }}</small><div class="bubble"><pre>{{ message.content }}</pre></div></div><div v-if="message.role === 'user'" class="avatar user">您</div></div>
          <div v-if="asking" class="message"><div class="avatar">✦</div><div class="bubble typing"><i /><i /><i /></div></div>
        </div>
        <div class="composer-wrap"><div class="source-line"><span>本次启用</span><em v-if="capabilities.vector">⌁ 向量</em><em v-if="capabilities.graph">⌘ Neo4j</em><em v-if="capabilities.web">◎ 联网</em></div><div class="composer"><textarea v-model="question" rows="2" :disabled="asking" maxlength="2000" placeholder="描述您的问题，支持医疗器械、公共卫生和法规检索…" @keydown.enter.exact.prevent="onAsk()" /><button class="send" :disabled="asking || !question.trim()" @click="onAsk">{{ asking ? '检索中' : '发送' }} ↑</button></div><div class="composer-foot"><span>Enter 发送 · Shift + Enter 换行</span><span>{{ question.length }}/2000</span></div></div>
      </main>
      <aside class="evidence-panel"><div class="evidence-heading"><div><strong>证据工作台</strong><small>回答生成后展示溯源依据</small></div><span class="tag">{{ result ? '已更新' : '等待中' }}</span></div><template v-if="result"><div class="metrics"><div><b>{{ result.contexts?.length || 0 }}</b><small>文本证据</small></div><div><b>{{ result.graph?.nodes?.length || 0 }}</b><small>图谱实体</small></div><div><b>{{ result.trace?.web_search?.result_count || 0 }}</b><small>网页结果</small></div></div><div v-if="result.trace?.route" class="route"><small>ROUTE INTENT</small><b>{{ result.trace.route.intent }}</b><span>{{ result.trace.route.reason || '已完成证据编排' }}</span></div><div v-if="result.graph?.keywords?.length" class="evidence-block"><h3>图谱关键词 <small>Neo4j</small></h3><div class="keywords"><button v-for="keyword in result.graph.keywords" :key="keyword" @click="openGraph(keyword)">{{ keyword }}</button></div></div><div v-if="result.contexts?.length" class="evidence-block"><h3>内部文档 <small>Milvus</small></h3><article v-for="context in result.contexts.slice(0, 4)" :key="context.rank"><b>[{{ context.rank }}] {{ context.metadata?.original_name || '知识库片段' }}</b><p>{{ context.text }}</p></article></div></template><div v-else class="evidence-empty"><strong>◌</strong><b>等待您的问题</b><span>路由信息与来源会集中显示在这里。</span></div></aside>
    </div>
  </div>
</template>

<style scoped>
.support-page{--ink:#172033;--subtle:#718096;--line:#e7ecf3;color:var(--ink);min-height:calc(100vh - 80px);background:#f8fafc;border:1px solid #e5eaf1;border-radius:20px;overflow:hidden}.support-header{padding:27px 32px 23px;background:linear-gradient(120deg,#fff,#f4f8ff);display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)}.eyebrow{color:#4775cb;font-size:10px;letter-spacing:.16em;font-weight:800}.live-dot{display:inline-block;width:7px;height:7px;background:#3da879;border-radius:50%;margin-right:7px}.support-header h1{margin:8px 0 3px;font-size:24px;letter-spacing:-.04em}.support-header p{color:var(--subtle);font-size:13px;margin:0}.header-actions{display:flex;align-items:center;gap:15px;color:var(--subtle);font-size:12px}.workspace{display:grid;grid-template-columns:246px minmax(420px,1fr) 295px;min-height:690px}.control-panel,.evidence-panel{background:#fff}.control-panel{border-right:1px solid var(--line)}.evidence-panel{border-left:1px solid var(--line);padding:22px 18px}.panel-section{padding:22px 18px;border-bottom:1px solid var(--line)}.section-heading{display:flex;justify-content:space-between;align-items:center;font-size:13px}.help{color:var(--subtle);font-size:11px;line-height:1.5;margin:7px 0 14px}.tag{display:inline-flex;padding:3px 8px;border-radius:20px;background:#f1f4f8;color:#798597;font-size:10px;font-weight:700}.tag-success{color:#19805b;background:#e8f8f0}.capability{width:100%;padding:10px 9px;display:flex;align-items:center;gap:9px;border:1px solid transparent;background:transparent;border-radius:10px;text-align:left;cursor:pointer}.capability:hover,.capability.active{background:#f6f9ff;border-color:#dce8ff}.cap-icon{width:29px;height:29px;display:grid;place-items:center;border-radius:8px;background:#eff3f8;color:#4778d8;font-size:18px}.cap-copy{flex:1;display:flex;flex-direction:column;gap:1px}.cap-copy b{font-size:12px}.cap-copy small{color:var(--subtle);font-size:10px}.switch{width:24px;height:14px;border-radius:10px;background:#dbe1e9;position:relative}.switch:after{content:'';width:10px;height:10px;border-radius:50%;position:absolute;top:2px;left:2px;background:#fff;transition:transform .15s}.active .switch{background:#4d80e8}.active .switch:after{transform:translateX(10px)}.muted,.section-heading .muted{color:var(--subtle);font-size:11px}.field-label{display:block;color:var(--subtle);font-size:11px;margin:15px 0 6px}.compact{padding:7px 9px;font-size:12px}.doc-list{max-height:165px;overflow:auto}.doc-row{display:flex;align-items:center;gap:6px;padding:7px 0;font-size:11px}.doc-row input{accent-color:#4778d8}.doc-name{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.empty{color:#9aa5b4;font-size:11px;padding:12px 0}.text-button{border:0;padding:8px 0 0;color:#4778d8;background:none;cursor:pointer;font-size:11px}.health{display:flex;flex-direction:column;gap:11px;color:var(--subtle);font-size:11px}.health b{color:#19805b;float:right}.health .offline{color:#bc7b27}.chat-panel{min-width:0;display:flex;flex-direction:column;background:#fbfcfe}.chat-toolbar{display:flex;justify-content:space-between;align-items:center;padding:17px 25px;background:#fff;border-bottom:1px solid var(--line);font-size:13px}.chat-toolbar strong span,.chat-toolbar small{color:#a0aaba;font-size:10px}.chat-body{flex:1;min-height:400px;max-height:570px;overflow:auto;padding:30px 27px}.welcome{max-width:490px;margin:25px auto;text-align:center}.welcome-mark{width:52px;height:52px;display:grid;place-items:center;margin:0 auto 16px;color:#5381dc;font-size:23px;background:#edf3ff;border-radius:16px}.welcome h2{font-size:19px;margin:0 0 8px}.welcome p{color:var(--subtle);font-size:12px;line-height:1.7;margin:0 auto 22px}.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.suggestions button{border:1px solid var(--line);background:#fff;border-radius:9px;padding:11px;text-align:left;color:#58677c;font-size:11px;cursor:pointer}.suggestions button:last-child{grid-column:span 2}.message{display:flex;gap:10px;margin-bottom:21px;align-items:flex-start}.message.user{justify-content:flex-end}.avatar{flex:0 0 29px;height:29px;border-radius:9px;display:grid;place-items:center;font-size:11px;background:#eaf1ff;color:#4e7bd3}.avatar.user{background:#303c51;color:#fff}.message-main{max-width:78%}.message-main>small{color:#9aa5b4;font-size:10px}.bubble{border:1px solid var(--line);background:#fff;border-radius:4px 13px 13px 13px;padding:12px 14px;margin-top:5px;box-shadow:0 3px 12px #28374b08}.bubble pre{white-space:pre-wrap;font:inherit;font-size:12px;line-height:1.7;margin:0}.user .bubble{background:#eaf1ff;border-color:#dbe8ff;border-radius:13px 4px 13px 13px}.typing{display:flex;gap:4px;padding:16px}.typing i{width:5px;height:5px;background:#91a0b5;border-radius:50%}.composer-wrap{background:#fff;border-top:1px solid var(--line);padding:12px 22px 16px}.source-line{display:flex;gap:6px;align-items:center;margin-bottom:7px;color:#a0aaba;font-size:10px}.source-line em{font-style:normal;background:#f2f5f9;border-radius:12px;padding:3px 8px;color:#60708a}.composer{border:1px solid #dce3ec;border-radius:11px;display:flex;align-items:flex-end;padding:6px;box-shadow:0 4px 14px #25374e0d}.composer textarea{resize:none;flex:1;border:0;outline:0;padding:8px;font-size:12px;background:transparent}.send{border:0;background:#4778d8;color:#fff;border-radius:8px;padding:9px 11px;font-size:11px;cursor:pointer}.send:disabled{opacity:.5}.composer-foot{display:flex;justify-content:space-between;padding:5px 3px 0;color:#a0aaba;font-size:10px}.evidence-heading{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:17px;border-bottom:1px solid var(--line)}.evidence-heading strong,.evidence-heading small{display:block}.evidence-heading strong{font-size:13px}.evidence-heading small{color:#a0aaba;font-size:10px;margin-top:4px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);padding:15px 0;border-bottom:1px solid var(--line)}.metrics div{text-align:center}.metrics b{display:block;color:#4778d8;font-size:18px}.metrics small{color:var(--subtle);font-size:9px}.route{background:#f5f8ff;border:1px solid #e2eaff;border-radius:8px;padding:11px;margin:15px 0;display:flex;flex-direction:column;gap:3px}.route>*{display:block}.route small{color:#6484c6;font-size:9px;letter-spacing:.12em}.route b{font-size:13px}.route span{color:var(--subtle);font-size:10px}.evidence-block{margin-top:18px}.evidence-block h3{font-size:11px;margin:0 0 8px}.evidence-block h3 small{float:right;color:#9aa5b4;font-weight:500}.keywords{display:flex;flex-wrap:wrap;gap:5px}.keywords button{border:1px solid #e1e8f2;background:#fff;border-radius:5px;padding:4px 7px;color:#58719c;font-size:10px;cursor:pointer}.evidence-block article{border:1px solid var(--line);background:#fff;border-radius:7px;padding:9px;margin-bottom:7px}.evidence-block article b{color:#6981ad;font-size:10px}.evidence-block article p{color:#778397;font-size:10px;line-height:1.55;margin:5px 0 0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.evidence-empty{color:#a0aaba;text-align:center;margin-top:155px;display:flex;flex-direction:column;align-items:center;gap:7px;font-size:11px}.evidence-empty strong{color:#7d9cdb;font-size:38px}.evidence-empty b{color:#748196;font-size:12px}.btn{height:34px;padding:0 13px;border-radius:8px;border:1px solid #dfe5ed;background:#fff;cursor:pointer;font-size:11px;color:#53647a}.btn:disabled{opacity:.6}@media(max-width:1100px){.workspace{grid-template-columns:220px minmax(400px,1fr)}.evidence-panel{display:none}}@media(max-width:700px){.support-header{padding:20px;align-items:flex-start;gap:12px;flex-direction:column}.workspace{display:block}.control-panel{border-right:0;border-bottom:1px solid var(--line)}.panel-section:not(:first-child){display:none}.chat-body{padding:20px 14px}.support-header h1{font-size:20px}.suggestions{grid-template-columns:1fr}.suggestions button:last-child{grid-column:auto}.header-actions{width:100%;justify-content:space-between}}
</style>
