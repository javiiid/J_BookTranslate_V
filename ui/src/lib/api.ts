/**
 * Typed bindings for the Python backend.
 *
 * Every shape here was captured from a live response in
 * `docs/inventory/` (Phase 0), not guessed. When the backend contract changes,
 * `npm run check:api` re-captures and the diff shows the drift.
 */

export type JobStatus =
  | 'queued'
  | 'running'
  | 'stopping'
  | 'paused'
  | 'stopped'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type Health = 'green' | 'yellow' | 'red'

export interface HealthPayload {
  status: 'ready' | 'error'
  message: string
}

export interface DashboardSummary {
  active_jobs: number
  paused_jobs: number
  completed_jobs: number
  failed_jobs: number
  total_books: number
  storage_free: number
  api_status: string
  estimated_cost: number
}

export interface Job {
  id: string
  filename: string
  filetype: string
  file_size: number
  source_language: string
  target_language: string
  model: string
  mode: string
  status: JobStatus
  created_at: string
  started_at: string | null
  updated_at: string
  output_path: string | null
  progress: { completed: number; total: number; percent: number }
  health: Health
  eta_seconds: number
  chunks_per_minute: number
  log: string
  error: string | null
  can_stop: boolean
  can_cancel: boolean
  can_resume: boolean
  rescue: string
  assets: Record<string, string>
  qa_report: string | null
  quality: Record<string, number> | null
  style: string
  download?: string
  asset_downloads?: Record<string, string>
  reader?: string
}

export interface JobChunk {
  id: string
  chapter: string
  source: string
  target: string
  flagged: boolean
}

export interface JobEvent {
  job_id?: string
  level: string
  event: string
  message: string
  timestamp: string
  recoverable?: boolean | number
}

export interface JobListResponse {
  items: Job[]
  total: number
}

export interface ChunksResponse {
  items: JobChunk[]
  total: number
  available: boolean
  translated: number
}

export interface Chapter {
  id: number
  title: string
  path: string
}

export interface ChapterContent {
  id: number
  title: string
  /** Already sanitised by the Python `sanitize_html` boundary. Render with
       dangerouslySetInnerHTML and never re-sanitise on this side. */
  html: string
}

export interface ChapterBlock {
  id: string
  position: number
  original: string
  translation: string
  original_html: string
  translation_html: string
}

export interface Model {
  id: string
  provider: string
  available: boolean
}

export interface Language {
  code: string
  name: string
}

export interface ReadingSettings {
  study_night_mode: boolean
  reading_theme: 'light' | 'dark'
  reading_mode: 'translation' | 'original' | 'bilingual'
  reading_font_size: number
  reading_line_height: number
  reading_width: number
  reading_direction: 'auto' | 'ltr' | 'rtl'
  reading_last_location: string | null
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  const text = await response.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!response.ok) {
    const message =
      body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
        ? body.error
        : `HTTP ${response.status}`
    throw new ApiError(message, response.status)
  }
  return body as T
}

export const api = {
  health: () => request<HealthPayload>('/api/health'),
  healthVerify: () => request<HealthPayload>('/api/health?verify=1'),
  summary: () => request<DashboardSummary>('/api/dashboard/summary'),

  jobs: () => request<JobListResponse>('/api/jobs'),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  jobChunks: (id: string) => request<ChunksResponse>(`/api/jobs/${encodeURIComponent(id)}/chunks`),
  jobLogs: (id: string) => request<{ items: JobEvent[] }>(`/api/jobs/${encodeURIComponent(id)}/logs`),
  jobAction: (id: string, action: 'stop' | 'resume' | 'cancel' | 'rescue') =>
    request<{ download?: string; message?: string }>(
      `/api/jobs/${encodeURIComponent(id)}/${action}`,
      { method: 'POST' },
    ),

  readerChapters: (id: string) =>
    request<{ book: string; items: Chapter[] }>(`/api/reader/${encodeURIComponent(id)}/chapters`),
  readerChapter: (id: string, chapterId: number) =>
    request<ChapterContent>(`/api/reader/${encodeURIComponent(id)}/chapters/${chapterId}`),
  readerBlocks: (id: string, chapterId: number) =>
    request<{ items: ChapterBlock[] }>(`/api/reader/${encodeURIComponent(id)}/chapters/${chapterId}/blocks`),
  readerSettings: () => request<{ value: ReadingSettings }>('/api/reader/settings'),

  models: () => request<{ items: Model[] }>('/api/models'),
  languages: () => request<{ items: Language[] }>('/api/languages'),
}
