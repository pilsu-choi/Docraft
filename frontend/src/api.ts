import type { AiStatus, Document, Format, ParseOptions, Project, Schema } from './types'

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const key = sessionStorage.getItem('docraft_api_key')
  const headers = new Headers(init?.headers)
  if (key) headers.set('X-API-Key', key)
  const response = await fetch(`/api${path}`, { ...init, headers })
  // FastAPI detail은 문자열, 검증 오류 배열, 또는 {message} 객체로 온다.
  const detail = !response.ok && (await response.json().catch(() => null))?.detail
  if (!response.ok) throw new Error(Array.isArray(detail) ? detail.map(item => String(item.msg).replace(/^Value error, /, '')).join(' ') : detail?.message || detail || `요청 실패 (${response.status})`)
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
const file = async (path: string) => {
  const key = sessionStorage.getItem('docraft_api_key')
  const response = await fetch(`/api${path}`, { headers: key ? { 'X-API-Key': key } : {} })
  if (!response.ok) throw new Error(`파일 요청 실패 (${response.status})`)
  return response
}
// Content-Disposition의 filename*=UTF-8''… → filename=… 순으로 파일명을 고르고, 없으면 fallback을 쓴다.
const save = async (path: string, fallback: string) => {
  const response = await file(path), header = response.headers.get('Content-Disposition') || ''
  const encoded = header.match(/filename\*=UTF-8''([^;]+)/i)?.[1], plain = header.match(/filename="?([^";]+)"?/i)?.[1]
  const url = URL.createObjectURL(await response.blob()), anchor = document.createElement('a')
  anchor.href = url; anchor.download = encoded ? decodeURIComponent(encoded) : plain || fallback; anchor.click(); URL.revokeObjectURL(url)
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const api = {
  aiStatus: () => request<AiStatus>('/ai/status'),
  projects: () => request<Project[]>('/projects'), createProject: (name: string, description?: string) => request<Project>('/projects', json('POST', { name, description })),
  project: (id: string) => request<Project>(`/projects/${id}`), updateProject: (id: string, name: string) => request<Project>(`/projects/${id}`, json('PATCH', { name })), deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  documents: (projectId: string) => request<Document[]>(`/projects/${projectId}/documents`), document: (id: string) => request<Document>(`/documents/${id}`), deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' }),
  // 파일마다 한 요청으로 보낸다. nginx가 요청 본문을 30MB로 막아 스캔 이미지 수십 장을 한 번에 보내면 413이 난다(파일 1개 상한은 25MB).
  upload: async (projectId: string, files: File[]) => {
    const created: Document[] = []
    for (const file of files) { const body = new FormData(); body.append('files', file); created.push(...await request<Document[]>(`/projects/${projectId}/documents`, { method: 'POST', body })) }
    return created
  },
  parse: (id: string, options: ParseOptions = {}) => request<Document>(`/documents/${id}/parse`, json('POST', options)),
  schemas: (projectId: string) => request<Schema[]>(`/projects/${projectId}/schemas`), createSchema: (projectId: string, name: string, json_schema: Record<string, unknown>) => request<Schema>(`/projects/${projectId}/schemas`, json('POST', { name, json_schema })),
  updateSchema: (id: string, name: string, json_schema: Record<string, unknown>) => request<Schema>(`/schemas/${id}`, json('PATCH', { name, json_schema })), deleteSchema: (id: string) => request<void>(`/schemas/${id}`, { method: 'DELETE' }),
  generateSchema: (projectId: string, prompt: string, document_ids: string[]) => request<Schema>(`/projects/${projectId}/schemas/generate`, json('POST', { prompt, document_ids })),
  extract: (id: string, schema_id: string) => request<Document>(`/documents/${id}/extract`, json('POST', { schema_id })), review: (id: string, path: string, value: unknown) => request<Document>(`/documents/${id}/review`, json('PATCH', { path, value })), approve: (id: string) => request<Document>(`/documents/${id}/approve`, { method: 'POST' }),
  extractBatch: (projectId: string, schema_id: string, document_ids: string[]) => request<{ queued: string[]; skipped: { id: string; filename: string; reason: string }[] }>(`/projects/${projectId}/extract`, json('POST', { schema_id, document_ids })),
  file: (id: string) => file(`/documents/${id}/file`).then(response => response.blob()),
  download: (id: string, format: Format) => save(`/documents/${id}/export?format=${format}`, `docraft-${id}.${format}`),
  downloadProject: (projectId: string, format: Format, schemaId?: string) => save(`/projects/${projectId}/export?format=${format}${schemaId ? `&schema_id=${schemaId}` : ''}`, `docraft-${projectId}.${format}`),
  setApiKey: (key: string) => key ? sessionStorage.setItem('docraft_api_key', key) : sessionStorage.removeItem('docraft_api_key')
}
