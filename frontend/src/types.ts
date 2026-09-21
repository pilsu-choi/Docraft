export type Status = 'uploaded' | 'queued' | 'parsing' | 'parsed' | 'extracting' | 'validating' | 'needs_review' | 'completed' | 'failed'
export type Project = { id: string; name: string; description?: string; created_at: string }
export type AiStatus = { configured: boolean; provider: string | null; model: string | null; mode: 'provider' | 'local'; ocr?: { configured: boolean; provider: string | null; model: string; ready: boolean; mode?: 'library' | 'paddle' } }
export type Schema = { id: string; project_id: string; name: string; version: number; json_schema: Record<string, unknown>; created_at: string }
export type Block = { type: string; text: string; page?: number; bbox?: number[]; page_size?: number[]; rows?: string[][] }
export type Grounding = { path: string; page?: number; bbox?: number[]; text?: string; confidence?: number; status?: string }
export type Document = { id: string; project_id: string; filename: string; media_type: string; size: number; status: Status; error?: string; markdown?: string; blocks?: Block[]; result?: unknown; groundings?: Grounding[]; validation?: unknown; corrections?: unknown[]; created_at: string; updated_at: string }
