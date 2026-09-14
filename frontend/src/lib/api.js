const baseUrl = () => (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

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

export function askQuestion({ question, document_ids, top_k }) {
  return apiFetch('/api/qa/ask/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, document_ids, top_k })
  })
}

export function listTasks() {
  return apiFetch('/api/monitoring/tasks/')
}

export function getTask(id) {
  return apiFetch(`/api/monitoring/tasks/${id}/`)
}

export function getOllamaStatus() {
  return apiFetch('/api/qa/ollama/status/')
}
