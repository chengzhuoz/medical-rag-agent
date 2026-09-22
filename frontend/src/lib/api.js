const baseUrl = () => {
  const fallback = import.meta.env.DEV ? 'http://127.0.0.1:8000' : window.location.origin
  return (import.meta.env.VITE_API_BASE_URL || fallback).replace(/\/+$/, '')
}

const joinUrl = (p) => {
  const path = String(p || '').replace(/^\/+/, '')
  return `${baseUrl()}/${path}`
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export async function apiFetch(path, options = {}) {
  const url = joinUrl(path)
  const resp = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {})
    }
  })

  const ct = resp.headers.get('content-type') || ''
  const isJson = ct.includes('application/json')
  const payload = isJson ? await resp.json().catch(() => null) : await resp.text().catch(() => '')

  if (!resp.ok) {
    const msg = (payload && payload.detail) || `请求失败（${resp.status}）`
    throw new ApiError(msg, resp.status, payload)
  }

  return payload
}

export function uploadDocument(file) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch('/api/documents/', { method: 'POST', body: fd })
}

export function listDocuments() {
  return apiFetch('/api/documents/')
}

export function getDocument(id) {
  return apiFetch(`/api/documents/${id}/`)
}

export function parseDocument(id) {
  return apiFetch(`/api/documents/${id}/parse/`, { method: 'POST' })
}

export function embedDocument(id) {
  return apiFetch(`/api/qa/embed/${id}/`, { method: 'POST' })
}

export function buildKgForDocument(id) {
  return apiFetch(`/api/kg/build/${id}/`, { method: 'POST' })
}

export function kgSearch(q, limit = 12) {
  return apiFetch(`/api/kg/search/?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`)
}

export function kgSubgraph(center, limit = 80) {
  return apiFetch(`/api/kg/subgraph/?center=${encodeURIComponent(center)}&limit=${encodeURIComponent(limit)}`)
}

export function askQuestion({ question, document_ids, top_k, use_vector = true, use_graph = true, use_web = true, conversation_id, memory_scope_id, memory_enabled = true }) {
  return apiFetch('/api/qa/ask/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, document_ids, top_k, use_vector, use_graph, use_web, conversation_id, memory_scope_id, memory_enabled })
  })
}

/**
 * 消费后端 SSE 问答流。事件仅包含可审计的运行阶段和回答片段，
 * 不传输或展示模型的隐式推理过程。
 */
export async function askQuestionStream(payload, handlers = {}) {
  const response = await fetch(joinUrl('/api/qa/ask/stream/'), {
    method: 'POST',
    headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    const errorPayload = await response.json().catch(() => null)
    throw new ApiError(errorPayload?.detail || `请求失败（${response.status}）`, response.status, errorPayload)
  }

  const decoder = new TextDecoder('utf-8')
  const reader = response.body.getReader()
  let buffer = ''

  const dispatch = (frame) => {
    const lines = frame.replace(/\r/g, '').split('\n')
    const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message'
    const rawData = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')
    if (!rawData) return
    let data
    try { data = JSON.parse(rawData) } catch { return }
    if (event === 'progress') handlers.onProgress?.(data)
    if (event === 'token') handlers.onToken?.(data.token || '')
    if (event === 'complete') handlers.onComplete?.(data)
    if (event === 'error') throw new ApiError(data.detail || '流式问答失败', 500, data)
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const frames = buffer.split(/\n\n/)
    buffer = frames.pop() || ''
    frames.forEach(dispatch)
    if (done) break
  }
  if (buffer.trim()) dispatch(buffer)
}

export function getMemoryOverview(memoryScopeId) {
  return apiFetch(`/api/qa/memory/overview/?memory_scope_id=${encodeURIComponent(memoryScopeId)}`)
}

export function clearMemory(memoryScopeId) {
  return apiFetch('/api/qa/memory/clear/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memory_scope_id: memoryScopeId })
  })
}

export function listTasks() {
  return apiFetch('/api/monitoring/tasks/')
}

export function getTask(id) {
  return apiFetch(`/api/monitoring/tasks/${id}/`)
}

export function getObservabilityOverview() {
  return apiFetch('/api/monitoring/overview/')
}

export function getOllamaStatus() {
  return apiFetch('/api/qa/ollama/status/')
}