<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../lib/api'
import ToastHost from '../components/ToastHost.vue'

const toast = ref(null)
const loading = ref(false)
const query = ref('')
const hits = ref([])

const graph = reactive({
  nodes: [],
  edges: []
})

const view = reactive({
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  dragging: null,
  panning: false,
  panStart: null
})

const panel = ref(null)
const selected = ref(null)
const viewportW = ref(window.innerWidth || 1200)
const isSingle = computed(() => viewportW.value <= 900)
const route = useRoute()

const setToast = (text) => {
  toast.value = { text }
  setTimeout(() => {
    toast.value = null
  }, 2200)
}

const apiSearch = async () => {
  const q = query.value.trim()
  if (!q) return
  loading.value = true
  try {
    const r = await apiFetch(`/api/kg/search/?q=${encodeURIComponent(q)}&limit=12`)
    if (r && r.ok === false) {
      hits.value = []
      setToast(r.error || 'Neo4j 未配置或不可用')
      return
    }
    hits.value = r.entities || []
    if (!hits.value.length) setToast('未找到匹配实体')
  } catch (e) {
    setToast(e.message || '搜索失败')
  } finally {
    loading.value = false
  }
}

const loadSubgraph = async (center) => {
  if (!center) return
  loading.value = true
  try {
    const r = await apiFetch(`/api/kg/subgraph/?center=${encodeURIComponent(center)}&limit=80`)
    if (r && r.ok === false) {
      graph.nodes = []
      graph.edges = []
      selected.value = null
      setToast(r.error || 'Neo4j 未配置或不可用')
      return
    }
    graph.nodes = r.nodes || []
    graph.edges = r.edges || []
    selected.value = center
    resetLayout()
  } catch (e) {
    setToast(e.message || '加载子图失败')
  } finally {
    loading.value = false
  }
}

const width = ref(980)
const height = ref(520)

const updateSize = () => {
  const el = panel.value
  if (!el) return
  const full = Math.max(320, el.clientWidth)
  const sideW = viewportW.value <= 900 ? 0 : 240
  width.value = Math.max(320, full - sideW)
  height.value = Math.max(320, Math.min(620, Math.round(window.innerHeight * 0.62)))
}

const nodesWithPos = reactive(new Map())

const resetLayout = () => {
  updateSize()
  view.scale = 1
  view.offsetX = width.value / 2
  view.offsetY = height.value / 2
  nodesWithPos.clear()
  const n = graph.nodes.length || 1
  const R = Math.min(width.value, height.value) * 0.32
  for (let i = 0; i < graph.nodes.length; i++) {
    const id = graph.nodes[i].id
    const a = (i / n) * Math.PI * 2
    nodesWithPos.set(id, { x: Math.cos(a) * R, y: Math.sin(a) * R, vx: 0, vy: 0 })
  }
  startSim()
}

let simHandle = 0
const startSim = () => {
  cancelAnimationFrame(simHandle)
  const tick = () => {
    stepSim()
    simHandle = requestAnimationFrame(tick)
  }
  simHandle = requestAnimationFrame(tick)
}

const stepSim = () => {
  const kRepel = 2200
  const kLink = 0.012
  const damp = 0.86
  const centerPull = 0.0015
  const ids = graph.nodes.map((n) => n.id)
  for (let i = 0; i < ids.length; i++) {
    const pi = nodesWithPos.get(ids[i])
    if (!pi) continue
    for (let j = i + 1; j < ids.length; j++) {
      const pj = nodesWithPos.get(ids[j])
      if (!pj) continue
      const dx = pi.x - pj.x
      const dy = pi.y - pj.y
      const d2 = dx * dx + dy * dy + 0.01
      const f = kRepel / d2
      const fx = (dx / Math.sqrt(d2)) * f
      const fy = (dy / Math.sqrt(d2)) * f
      pi.vx += fx
      pi.vy += fy
      pj.vx -= fx
      pj.vy -= fy
    }
  }

  for (const e of graph.edges) {
    const a = nodesWithPos.get(e.source)
    const b = nodesWithPos.get(e.target)
    if (!a || !b) continue
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.sqrt(dx * dx + dy * dy) + 0.001
    const target = 120 + Math.min(180, (e.weight || 1) * 8)
    const diff = dist - target
    const fx = (dx / dist) * diff * kLink
    const fy = (dy / dist) * diff * kLink
    a.vx += fx
    a.vy += fy
    b.vx -= fx
    b.vy -= fy
  }

  for (const id of ids) {
    const p = nodesWithPos.get(id)
    if (!p) continue
    if (view.dragging && view.dragging.id === id) continue
    p.vx += -p.x * centerPull
    p.vy += -p.y * centerPull
    p.vx *= damp
    p.vy *= damp
    p.x += p.vx
    p.y += p.vy
  }
}

const toScreen = (x, y) => {
  return { sx: x * view.scale + view.offsetX, sy: y * view.scale + view.offsetY }
}

const fromScreen = (sx, sy) => {
  return { x: (sx - view.offsetX) / view.scale, y: (sy - view.offsetY) / view.scale }
}

const findNodeAt = (sx, sy) => {
  const pt = fromScreen(sx, sy)
  for (const n of graph.nodes) {
    const p = nodesWithPos.get(n.id)
    if (!p) continue
    const dx = p.x - pt.x
    const dy = p.y - pt.y
    const r = 16 / view.scale
    if (dx * dx + dy * dy <= r * r) return n
  }
  return null
}

const onWheel = (ev) => {
  ev.preventDefault()
  const delta = ev.deltaY > 0 ? 0.92 : 1.08
  const prev = view.scale
  view.scale = Math.min(2.2, Math.max(0.45, view.scale * delta))
  const rect = ev.currentTarget.getBoundingClientRect()
  const sx = ev.clientX - rect.left
  const sy = ev.clientY - rect.top
  const before = fromScreen(sx, sy)
  view.offsetX = sx - before.x * view.scale
  view.offsetY = sy - before.y * view.scale
  if (prev === view.scale) return
}

const onPointerDown = (ev) => {
  const rect = ev.currentTarget.getBoundingClientRect()
  const sx = ev.clientX - rect.left
  const sy = ev.clientY - rect.top
  const node = findNodeAt(sx, sy)
  if (node) {
    const p = nodesWithPos.get(node.id)
    view.dragging = { id: node.id, node, start: { ...p }, startPt: { sx, sy } }
    ev.currentTarget.setPointerCapture(ev.pointerId)
  } else {
    view.panning = true
    view.panStart = { sx, sy, ox: view.offsetX, oy: view.offsetY }
    ev.currentTarget.setPointerCapture(ev.pointerId)
  }
}

const onPointerMove = (ev) => {
  const rect = ev.currentTarget.getBoundingClientRect()
  const sx = ev.clientX - rect.left
  const sy = ev.clientY - rect.top
  if (view.dragging) {
    const p = nodesWithPos.get(view.dragging.id)
    if (!p) return
    const pt = fromScreen(sx, sy)
    p.x = pt.x
    p.y = pt.y
    p.vx = 0
    p.vy = 0
  } else if (view.panning && view.panStart) {
    view.offsetX = view.panStart.ox + (sx - view.panStart.sx)
    view.offsetY = view.panStart.oy + (sy - view.panStart.sy)
  }
}

const onPointerUp = (ev) => {
  const rect = ev.currentTarget.getBoundingClientRect()
  const sx = ev.clientX - rect.left
  const sy = ev.clientY - rect.top
  if (view.dragging) {
    const node = findNodeAt(sx, sy)
    if (node) selected.value = node.id
  }
  view.dragging = null
  view.panning = false
  view.panStart = null
}

const selectedNode = computed(() => graph.nodes.find((n) => n.id === selected.value) || null)
const neighbors = computed(() => {
  if (!selected.value) return []
  const out = []
  for (const e of graph.edges) {
    if (e.source === selected.value) out.push({ id: e.target, w: e.weight || 1 })
    if (e.target === selected.value) out.push({ id: e.source, w: e.weight || 1 })
  }
  return out.sort((a, b) => b.w - a.w).slice(0, 12)
})

const shortLabel = (s) => {
  const t = String(s || '')
  return t.length > 10 ? t.slice(0, 10) + '…' : t
}

onMounted(() => {
  const onResize = () => {
    viewportW.value = window.innerWidth || 1200
    updateSize()
  }
  window.addEventListener('resize', onResize)
  updateSize()
  const center = route.query.center
  if (typeof center === 'string' && center.trim()) {
    query.value = center.trim()
    apiSearch().then(() => {
      if (hits.value && hits.value.length) loadSubgraph(hits.value[0])
    })
  }
})
</script>

<template>
  <ToastHost :model-value="toast" />
  <div class="grid">
    <section class="card">
      <div class="card-hd">
        <h2 class="title">知识图谱</h2>
        <div class="muted" style="font-size: 12px">Neo4j 实体与共现关系，可搜索并查看局部结构</div>
      </div>
      <div class="card-bd">
        <div class="row" style="justify-content: space-between; width: 100%">
          <div class="row" style="flex: 1; min-width: 240px">
            <input class="field" v-model="query" placeholder="输入关键词，例如：糖尿病肾病、传染病" />
          </div>
          <div class="row">
            <button class="btn" :disabled="loading" @click="apiSearch">搜索</button>
            <button class="btn" :disabled="loading" @click="loadSubgraph(hits[0])" v-if="hits.length">载入首条</button>
          </div>
        </div>

        <div v-if="hits.length" class="hits">
          <button class="btn" v-for="h in hits" :key="h" @click="loadSubgraph(h)">{{ h }}</button>
        </div>
      </div>
    </section>

    <section class="card" ref="panel">
      <div class="card-hd">
        <h2 class="title">局部结构</h2>
        <div class="muted" style="font-size: 12px" v-if="selectedNode">{{ selectedNode.label }}</div>
      </div>
      <div class="card-bd" style="padding: 0">
        <div class="wrap" :style="{ height: height + 'px', gridTemplateColumns: isSingle ? '1fr' : '1fr 240px' }">
          <svg
            class="svg"
            :width="width"
            :height="height"
            @wheel="onWheel"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
          >
            <g>
              <text
                v-if="!graph.nodes || !graph.nodes.length"
                :x="Math.round(width / 2)"
                :y="Math.round(height / 2)"
                fill="rgba(16,19,26,0.55)"
                font-size="13"
                text-anchor="middle"
              >
                暂无图谱数据（请先配置 Neo4j 并构建图谱）
              </text>
              <line
                v-for="(e, idx) in graph.edges"
                :key="idx"
                :x1="toScreen(nodesWithPos.get(e.source)?.x || 0, nodesWithPos.get(e.source)?.y || 0).sx"
                :y1="toScreen(nodesWithPos.get(e.source)?.x || 0, nodesWithPos.get(e.source)?.y || 0).sy"
                :x2="toScreen(nodesWithPos.get(e.target)?.x || 0, nodesWithPos.get(e.target)?.y || 0).sx"
                :y2="toScreen(nodesWithPos.get(e.target)?.x || 0, nodesWithPos.get(e.target)?.y || 0).sy"
                stroke="rgba(16,19,26,0.14)"
                stroke-width="1"
              />

              <g v-for="n in graph.nodes" :key="n.id">
                <circle
                  :cx="toScreen(nodesWithPos.get(n.id)?.x || 0, nodesWithPos.get(n.id)?.y || 0).sx"
                  :cy="toScreen(nodesWithPos.get(n.id)?.x || 0, nodesWithPos.get(n.id)?.y || 0).sy"
                  :r="selected === n.id ? 9 : 7"
                  :fill="selected === n.id ? 'rgba(47,111,235,0.85)' : 'rgba(16,19,26,0.75)'"
                  :stroke="selected === n.id ? 'rgba(47,111,235,0.85)' : 'rgba(16,19,26,0.14)'"
                  stroke-width="1"
                />
                <text
                  :x="toScreen(nodesWithPos.get(n.id)?.x || 0, nodesWithPos.get(n.id)?.y || 0).sx + 12"
                  :y="toScreen(nodesWithPos.get(n.id)?.x || 0, nodesWithPos.get(n.id)?.y || 0).sy + 4"
                  fill="rgba(16,19,26,0.86)"
                  font-size="12"
                >
                  {{ shortLabel(n.label) }}
                </text>
              </g>
            </g>
          </svg>

          <div class="side" v-if="selectedNode">
            <div style="font-weight: 700">{{ selectedNode.label }}</div>
            <div class="muted" style="font-size: 12px; margin-top: 6px">邻居（按共现权重）</div>
            <div class="neighbors" v-if="neighbors.length">
              <button class="btn" v-for="x in neighbors" :key="x.id" @click="loadSubgraph(x.id)">{{ x.id }}</button>
            </div>
            <div v-else class="muted" style="margin-top: 8px">无邻居或未构建图谱。</div>
          </div>
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

.hits {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wrap {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 0;
}

.svg {
  background: rgba(16, 19, 26, 0.01);
  border-right: 1px solid var(--border);
  cursor: grab;
  touch-action: none;
}

.side {
  padding: 14px;
  height: 100%;
  overflow: auto;
}

.neighbors {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 900px) {
  .wrap {
    grid-template-columns: 1fr;
  }
  .svg {
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
}
</style>
