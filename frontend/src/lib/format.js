export function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function docStatusLabel(s) {
  const m = { uploaded: '已上传', parsed: '已解析', embedded: '已向量化', failed: '失败' }
  return m[s] || s || ''
}

export function taskStatusLabel(s) {
  const m = { running: '运行中', succeeded: '成功', failed: '失败' }
  return m[s] || s || ''
}

export function statusTagClass(s) {
  if (s === 'embedded' || s === 'succeeded') return 'tag tag-success'
  if (s === 'parsed' || s === 'running') return 'tag tag-warn'
  if (s === 'failed') return 'tag tag-danger'
  return 'tag'
}

