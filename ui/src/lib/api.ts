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

/* ------------------------------------------------------------------ */
/* Library                                                             */
/* ------------------------------------------------------------------ */

export interface LibraryVariant {
  id: number
  job_id: string
  path: string
  kind: string
  size_bytes: number
  created_at: string
  archived: number
  book_id: number
  display_name: string
  extension: string
  mime_type: string
  language: string
  checksum: string
  is_readable: number
  page_count: number
  chapter_count: number
  last_opened_at: string | null
  last_read_location: string | null
  status: string
  progress: { completed: number; total: number }
  error: string | null
  download: string
  reader: string
}

export interface LibraryBook {
  id: number
  title: string
  author: string
  cover_path: string | null
  created_at: string
  updated_at: string
  status: string
  variants: LibraryVariant[]
  size_bytes: number
  translated: boolean
  readable: boolean
}

export interface LibraryListResponse {
  items: LibraryBook[]
  total: number
  page: number
  limit: number
  storage: { used: number; free: number }
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

/* ------------------------------------------------------------------ */
/* Glossary — the propose / review / approve flow                      */
/* ------------------------------------------------------------------ */

/** An approved glossary entry. `origin` is 'approved' for terms the user
 *  promoted and 'proposed' for ones that reached the table by another route. */
export interface GlossaryTerm {
  source_term: string
  target_term: string
  kind: string
  notes: string
  origin?: string
}

export interface Glossary {
  book_id: number
  source_language: string
  target_language: string
  version: number
  terms: GlossaryTerm[]
}

export interface GlossaryProposal {
  book_id: number
  source_language: string
  target_language: string
  origin: 'preflight' | 'postrun'
  created_at: string | null
  terms: GlossaryTerm[]
}

/* ------------------------------------------------------------------ */
/* Provider configuration                                              */
/* ------------------------------------------------------------------ */

export interface ProviderConfig {
  base_url: string
  has_api_key: boolean
  default_model: string
  max_concurrency: number
}

export interface AnalyticsOverview {
  jobs: number
  completed_chunks: number
  input_tokens: number
  output_tokens: number
  /** Always 0.0: the provider layer does not persist token usage, so any
   *  number here would be invented. Surfaced honestly as absent, not as zero
   *  that reads like "free". */
  estimated_cost: number
  retries: number
}

/* ------------------------------------------------------------------ */
/* Account portal                                                      */
/* ------------------------------------------------------------------ */

export interface PortalAccount {
  id: number
  display_name: string
  email: string
  locale: string
  plan: string
  organization: string
  role: string
  credit_balance: number
  created_at: string
  updated_at: string
}

export interface PortalPlan {
  id: string
  name_fa: string
  name_en: string
  monthly_price: number
  features: string[]
}

export interface Transaction {
  id: number
  kind: string
  reference_id: string
  amount_usd: number
  credits: number
  status: string
  created_at: string
}

export interface AccountPortal {
  overview: {
    account: PortalAccount
    plan: PortalPlan
    counts: {
      books: number
      jobs: number
      completed_jobs: number
      glossaries: number
      memory_entries: number
      api_keys: number
      open_orders: number
    }
    transactions: Transaction[]
  }
  plans: PortalPlan[]
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
  providerConfig: () => request<ProviderConfig>('/api/provider-config'),

  /* --- library ------------------------------------------------------ */
  library: (page: number, limit: number, query = '') => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) })
    if (query.trim()) params.set('q', query.trim())
    return request<LibraryListResponse>(`/api/library?${params}`)
  },
  book: (id: number) => request<LibraryBook>(`/api/library/${id}`),
  archiveBook: (id: number) =>
    request<{ ok: boolean }>(`/api/library/${id}`, { method: 'DELETE' }),

  /* --- glossary ----------------------------------------------------- */
  /**
   * Upload a book and start translating it.
   *
   * The backend takes multipart form data rather than JSON, and the response
   * carries `book_id`, which is what the glossary flow needs. FormData is built
   * by hand rather than by `request` because that helper always sends JSON.
   */
  createJob: async (form: FormData): Promise<{ id: string; book_id: number | null; from_lang: string; to_lang: string }> => {
    const response = await fetch('/api/jobs', { method: 'POST', body: form })
    const text = await response.text()
    const body: unknown = text ? JSON.parse(text) : null
    if (!response.ok) {
      const message =
        body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
          ? body.error
          : `HTTP ${response.status}`
      throw new ApiError(message, response.status)
    }
    return body as { id: string; book_id: number | null; from_lang: string; to_lang: string }
  },

  glossary: (bookId: number, from: string, to: string) =>
    request<Glossary>(`/api/library/${bookId}/glossary?from=${from}&to=${to}`),
  proposal: (bookId: number, from: string, to: string, origin: 'preflight' | 'postrun' = 'preflight') =>
    request<GlossaryProposal>(
      `/api/library/${bookId}/glossary/proposal?from=${from}&to=${to}&origin=${origin}`,
    ),
  /** One LLM call over samples from across the book. Slow: 20-60 seconds. */
  proposeTerms: (bookId: number, body: { from_lang: string; to_lang: string; model?: string; origin?: 'preflight' | 'postrun' }) =>
    request<GlossaryProposal>(`/api/library/${bookId}/glossary/propose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  /** Promote the ticked terms into the live glossary; the draft is cleared. */
  approveProposal: (
    bookId: number,
    body: { from_lang: string; to_lang: string; origin?: 'preflight' | 'postrun'; approved: string[] },
  ) =>
    request<Glossary & { proposal_origin: string; approved_count: number }>(
      `/api/library/${bookId}/glossary/proposal/approve`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    ),

  /* --- account ------------------------------------------------------ */
  accountPortal: () => request<AccountPortal>('/api/account/portal'),
  analytics: () => request<AnalyticsOverview>('/api/analytics/overview'),
  logs: () => request<{ items: JobEvent[] }>('/api/logs'),
}
