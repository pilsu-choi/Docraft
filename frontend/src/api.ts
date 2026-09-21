import type { AiStatus, Document, Project, Schema } from './types'

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const key = sessionStorage.getItem('docraft_api_key')
  const headers = new Headers(init?.headers)
  if (key) headers.set('X-API-Key', key)
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `요청 실패 (${response.status})`)
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
const blob = async (path: string) => {
  const key = sessionStorage.getItem('docraft_api_key')
  const response = await fetch(`/api${path}`, { headers: key ? { 'X-API-Key': key } : {} })
  if (!response.ok) throw new Error(`파일 요청 실패 (${response.status})`)
  return response.blob()
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const api = {
  aiStatus: () => request<AiStatus>('/ai/status'),
  projects: () => request<Project[]>('/projects'), createProject: (name: string, description?: string) => request<Project>('/projects', json('POST', { name, description })),
  project: (id: string) => request<Project>(`/projects/${id}`), updateProject: (id: string, name: string) => request<Project>(`/projects/${id}`, json('PATCH', { name })), deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  documents: (projectId: string) => request<Document[]>(`/projects/${projectId}/documents`), document: (id: string) => request<Document>(`/documents/${id}`),
  upload: (projectId: string, files: File[]) => { const body = new FormData(); files.forEach(file => body.append('files', file)); return request<Document[]>(`/projects/${projectId}/documents`, { method: 'POST', body }) },
  parse: (id: string) => request<Document>(`/documents/${id}/parse`, { method: 'POST' }),
  schemas: (projectId: string) => request<Schema[]>(`/projects/${projectId}/schemas`), createSchema: (projectId: string, name: string, json_schema: Record<string, unknown>) => request<Schema>(`/projects/${projectId}/schemas`, json('POST', { name, json_schema })),
  updateSchema: (id: string, name: string, json_schema: Record<string, unknown>) => request<Schema>(`/schemas/${id}`, json('PATCH', { name, json_schema })), deleteSchema: (id: string) => request<void>(`/schemas/${id}`, { method: 'DELETE' }),
  generateSchema: (projectId: string, prompt: string, document_id?: string) => request<Schema>(`/projects/${projectId}/schemas/generate`, json('POST', { prompt, document_id })),
  extract: (id: string, schema_id: string) => request<Document>(`/documents/${id}/extract`, json('POST', { schema_id })), review: (id: string, path: string, value: unknown) => request<Document>(`/documents/${id}/review`, json('PATCH', { path, value })), approve: (id: string) => request<Document>(`/documents/${id}/approve`, { method: 'POST' }),
  file: (id: string) => blob(`/documents/${id}/file`),
  download: async (id: string, format: 'json' | 'csv') => {
    const value = await blob(`/documents/${id}/export?format=${format}`), url = URL.createObjectURL(value), anchor = document.createElement('a')
    anchor.href = url; anchor.download = `docraft-${id}.${format}`; anchor.click(); URL.revokeObjectURL(url)
  },
  setApiKey: (key: string) => key ? sessionStorage.setItem('docraft_api_key', key) : sessionStorage.removeItem('docraft_api_key')
}
