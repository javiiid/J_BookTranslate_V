/**
 * Typed bindings for the Python backend.
 *
 * Every shape here was captured from a live response in
 * `docs/inventory/` (Phase 0), not guessed. When the backend contract changes,
 * `npm run check:api` re-captures and the diff shows the drift.
 */
import type { AuthEvent, AuthMeResponse, AuthResponse, AuthSession } from './auth.ts'

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

/**
 * One approved glossary pair for in-reader highlighting, from
 * `GET /api/reader/:id/glossary`. The job's own snapshot — the same terms
 * the book was translated with — longest source first, capped at 40.
 */
export interface ReaderGlossaryTerm {
  source_term: string
  target_term: string
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
  /**
   * Reading shelf, owned by `app/library/shelves.py` — never the translation
   * `status`. Optional because an older backend predates it; absence renders
   * as "no shelf" rather than crashing.
   */
  shelf?: 'want' | 'reading' | 'finished' | null
  /** Custom tags for this user. Absent on older backends; renders as none. */
  tags?: string[]
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

/**
 * The buckets `/api/library` can be filtered on.
 *
 * These are the server's own strings, read out of `library_summary` in
 * `app/web.py`, and not a set invented here. The page's filter row is built
 * from this union, so a bucket the UI shows is a bucket the backend can filter
 * on -- the alternative is a tab that looks exact and is really a client-side
 * guess over one page of results.
 *
 * `archived` is understood by the endpoint and is deliberately absent from the
 * filter row: archiving is a per-book action, and a tab that hides books would
 * give a second, quieter way to lose one.
 */
export type LibraryStatusFilter = 'completed' | 'running' | 'failed' | 'available' | 'archived'

/**
 * Reading shelves from `app/library/shelves.py`. Separate from
 * `LibraryStatusFilter`, which is translation state — a book can be
 * translation-`completed` and still sit on no shelf at all.
 */
export type LibraryShelf = 'want' | 'reading' | 'finished'

/** Per-day page totals from `GET /api/reading/stats`. Empty library → zeros, never NaN. */
export interface ReadingStats {
  per_day: Array<{ day: string; pages: number }>
  total_pages: number
  avg_per_day: number
  streak_days: number
  days: number
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
  reading_mode: 'translation' | 'original' | 'bilingual' | 'columns'
  reading_font_size: number
  reading_line_height: number
  reading_width: number
  reading_direction: 'auto' | 'ltr' | 'rtl'
  /**
   * The chapter the server remembers, written as `{job_id, chapter}` by the
   * Python reader and by this port — not a string. Typed as `unknown`
   * because older rows may hold anything; narrow with `lastLocationOf`
   * in `lib/reading.ts` rather than trusting the shape.
   */
  reading_last_location: unknown
  /**
   * Present on the backend (`READING_DEFAULTS` in `app/web.py`); optional
   * here so payloads built before the glossary step still typecheck.
   */
  reading_glossary?: boolean
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
  /** Present in the response. Optional in the type because an older backend
   *  that predates the key table would omit it, and the page handles that by
   *  treating absence as an empty list rather than crashing. */
  api_keys?: PortalApiKey[]
  /** See `api_keys` for why these are optional. */
  marketplace?: MarketplaceItem[]
  orders?: unknown[]
  packages?: unknown[]
  publisher?: {
    books: number
    active_projects: number
    delivered: number
    estimated_spend: number
    languages?: unknown
  }
}

/**
 * An API key row from the portal.
 *
 * `name` is whatever is in the database column, and the endpoint returns it
 * verbatim. In this installation that column holds a string beginning with
 * `sk-`, which is shaped like a provider secret -- so the UI masks any name
 * that looks like one rather than printing it. See `maskSecretLike` in
 * `lib/format.ts`, and the note there about why the value should be fixed on
 * the server instead.
 */
export interface PortalApiKey {
  id: number
  name: string
  token_prefix: string
  scopes: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export type MarketplaceKind = 'glossary' | 'preset' | 'style' | string

/**
 * An installable pack from the marketplace.
 *
 * These are real files, not purchases: installing one copies a glossary into
 * this install. `installed` says whether that has already happened, and
 * `price_usd` is displayed but there is no checkout in a local install, so the
 * page does not offer to buy anything.
 */
export interface MarketplaceItem {
  id: string
  kind: MarketplaceKind
  title_fa: string
  title_en: string
  description_fa: string
  description_en: string
  owner_name: string
  language_pair: string
  price_usd: number
  rating: number
  installs: number
  featured: number
  active: number
  installed: number
}

/** The result of POST /api/provider-config/test.
 *
 * `models` is a count, not a list: the backend answers how many models the
 * provider listed (`len(model_ids)` in `app/web.py::_verify_provider_config`).
 * `selected_model` is the model that was tested. */
export interface ProviderTestResult {
  message: string
  base_url: string
  models: number
  selected_model: string
  /** Whether the chosen model appears in the provider's own list. */
  model_available?: boolean
}

/**
 * The pre-translation estimate, from POST /api/jobs/estimate.
 *
 * `estimated_cost.known` is the field that matters. The endpoint this replaced
 * returned a hardcoded `0.0`, which beside a "start translating" button reads as
 * "free" rather than "unknown". A model with no price on file now comes back with
 * `known: false`, and the UI has to say the price is unknown instead of printing
 * a number nobody can stand behind.
 *
 * `chunk_count_exact` says the count came from actually chunking the book. It is
 * false for a PDF or an unreadable file, where the count is derived from the page
 * count or the byte size, and the dialog says which it is.
 */
export interface TranslationEstimate {
  /** Chunks that will actually be billed. Less than `chunk_count_total` on a resume. */
  chunk_count: number
  /** Every chunk the book chunks into, translated or not. */
  chunk_count_total: number
  /** Chunks an unfinished job already has. 0 when there is no resume. */
  chunks_already_done: number
  token_count: number
  estimated_cost: {
    min: number
    max: number
    /**
     * The two parts summed, before the band. Carried at four decimals so the
     * breakdown on screen adds up to it: at cents, 0.05 + 0.03 is 0.08, not 0.09.
     *
     * The dialog used to render the total beside a badge reading
     * `+$0.12 شامل واژه‌نامه` -- a total that already included the glossary, beside
     * a sign inviting it to be added again. A reader who believed the badge got
     * a total $0.12 above the one on screen. These two fields are what make the
     * total checkable instead.
     */
    base: number
    /** The token cost alone. */
    translation: number
    /** The second LLM pass over every chunk. Zero when the glossary is off. */
    glossary: number
    currency: string
    known: boolean
  }
  /** Kept for callers that only want the glossary share. Mirrors `estimated_cost.glossary`. */
  glossary_cost: number
  /** A Persian duration, generated server-side. */
  estimated_time: string
  estimated_time_seconds: number
  source_lang: string
  target_lang: string
  model: string
  mode: string
  concurrency: number
  has_resume: boolean
  /** 0–1 when `has_resume`, else null. */
  resume_progress: number | null
  /** Chunks still to send on a resume. 0 when there is no resume. */
  resume_remaining: number
  chunk_count_exact: boolean
}

/**
 * What `POST /api/jobs/upload` returns.
 *
 * `upload_id` is NOT in that response. The route answers with `file_path`, a
 * full filesystem path, while `POST /api/calibrations` wants a bare filename:
 * it joins it to the upload directory itself and rejects anything containing a
 * separator, because the browser must not choose where on the server a file
 * lives. So the id is derived here, once, rather than each caller slicing the
 * path differently.
 */
export interface UploadedBook {
  /** The stored file's name inside the upload directory. Derived, not sent. */
  upload_id: string
  file_path: string
  filename: string
  size: number
}

/** The last segment of a path, whether it was written with `/` or `\`. */
export function uploadIdFrom(filePath: string): string {
  return filePath.split(/[/\\]/).pop() ?? ''
}

/** The stored upload as the calibration route wants to receive it. */
export function withUploadId(stored: Omit<UploadedBook, 'upload_id'>): UploadedBook {
  return { ...stored, upload_id: uploadIdFrom(stored.file_path) }
}

/**
 * What `POST /api/jobs/rescue/import` returns.
 *
 * The chunk field names match `/api/jobs/estimate` on purpose, so the page reads
 * one vocabulary from both. A page that had to learn two spellings of "how many
 * chunks are in this book" would eventually read the wrong one -- and here the two
 * numbers differ, because one is the whole book and the other is what a resume
 * will actually bill.
 */
export interface RescueImport {
  id: string
  filename: string
  file_path: string
  from_lang: string
  to_lang: string
  model: string
  mode: string
  /** Always `paused`. Nothing is sent until the reader confirms the estimate. */
  status: string
  chunk_count_total: number
  chunks_already_done: number
  chunks_remaining: number
  /** The temp directory the resume reads. Useful in an error message. */
  resumed_from: string
}

/**
 * A book is already on the server, and the caller did not say to replace it.
 *
 * A distinct type rather than a flag on `ApiError`, because this one is a
 * question and the rest are failures. A rescue carries the settings it ran with,
 * so importing it over a queued book would silently change its language pair,
 * model or glossary -- and a different model means a different bill. The reader
 * decides.
 */
export class RescueConflictError extends Error {
  readonly conflict: RescueConflict

  constructor(message: string, conflict: RescueConflict) {
    super(message)
    this.name = 'RescueConflictError'
    this.conflict = conflict
  }
}

export interface RescueConflict {
  id: string
  status: string
  progress: { completed: number; total: number }
  rescued: { chunks_already_done: number; chunk_count_total: number }
  /**
   * Per setting, what the rescue says and what the server has. A `rescue` equal
   * to its `server` means nothing differs, and the page says so rather than
   * listing four identical lines.
   */
  differences: Record<string, { rescue: string; server: string }>
}

export interface EstimateRequest {
  file_path: string
  /** Every optional field admits `undefined` on purpose: this project compiles
   * with `exactOptionalPropertyTypes`, and "not specified" is the meaningful
   * value for all of them. The server then falls back to what is in
   * config.yaml, which is the honest request -- better than the client sending a
   * default it invented. */
  model?: string | undefined
  concurrency?: number | undefined
  mode?: 'fast' | undefined
  glossary_auto?: boolean | undefined
  from_lang?: string | undefined
  to_lang?: string | undefined
}


export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Parse a response body as JSON, throwing an `ApiError` — never a raw
 * `SyntaxError` — when the server (or a proxy between us and it) answers with
 * HTML instead. A 502 from Vite's proxy is the usual shape of this: without
 * the guard, every page's `error.message` handling shows a parser crash
 * rather than the failure it was meant to report.
 */
export function readJsonBody(text: string, status: number): unknown {
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new ApiError('پاسخ خوانا از سرور دریافت نشد.', status)
  }
}

function errorMessage(body: unknown, status: number): string {
  return body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
    ? body.error
    : `HTTP ${status}`
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  const text = await response.text()
  const body: unknown = readJsonBody(text, response.status)
  if (!response.ok) {
    throw new ApiError(errorMessage(body, response.status), response.status)
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
  /**
   * Approved glossary pairs for in-reader highlighting. Fetched once per
   * book and reused across chapters: the snapshot never changes mid-read.
   */
  readerGlossary: (id: string) =>
    request<{ items: ReaderGlossaryTerm[] }>(`/api/reader/${encodeURIComponent(id)}/glossary`),
  readerSettings: () => request<{ value: ReadingSettings }>('/api/reader/settings'),
  /**
   * Persist reader settings.
   *
   * The body is FLAT (`{reading_font_size: 20}`), not `{value: {...}}`: the
   * backend keeps only keys in `READING_DEFAULTS` and silently drops the rest,
   * so a nested shape returns `ok: true` while saving nothing. Unknown keys
   * are ignored server-side, so sending a partial object is safe.
   */
  updateReaderSettings: (patch: Partial<ReadingSettings>) =>
    request<{ ok: boolean; value: ReadingSettings }>('/api/reader/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),

  models: () => request<{ items: Model[] }>('/api/models'),
  languages: () => request<{ items: Language[] }>('/api/languages'),
  providerConfig: () => request<ProviderConfig>('/api/provider-config'),

  /* --- library ------------------------------------------------------ */
  library: (
    page: number,
    limit: number,
    query = '',
    // `''` is "no filter", which is what the endpoint already understands by
    // omission -- so it is a value here rather than an optional parameter, and a
    // caller cannot pass `undefined` where the union would not take it.
    status: LibraryStatusFilter | '' = '',
    // Same convention for the reading shelf and tag: omission means no filter.
    shelf: LibraryShelf | '' = '',
    tag = '',
  ) => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) })
    if (query.trim()) params.set('q', query.trim())
    if (status) params.set('status', status)
    if (shelf) params.set('shelf', shelf)
    if (tag.trim()) params.set('tag', tag.trim())
    return request<LibraryListResponse>(`/api/library?${params}`)
  },
  book: (id: number) => request<LibraryBook>(`/api/library/${id}`),
  /**
   * Move a book between reading shelves (`null` clears it). Unknown shelves
   * are a 400, never a silent fallback — the reader chose a word and the
   * server must either honour it or say so.
   */
  setShelf: (id: number, shelf: LibraryShelf | null) =>
    request<{ ok: boolean; shelf: LibraryShelf | null }>(`/api/library/${id}/shelf`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shelf }),
    }),
  /**
   * Replace a book's tags. Normalisation (trim, ZWNJ kept, Latin lowered)
   * lives server-side in `app/library/shelves.py`; this sends the raw list.
   */
  setTags: (id: number, tags: string[]) =>
    request<{ ok: boolean; tags: string[] }>(`/api/library/${id}/tags`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags }),
    }),
  /**
   * Add pages to today's reading total. Fire-and-forget from the reader:
   * a failed report must never block rendering the chapter.
   */
  reportProgress: (id: number, pages: number, location?: string) =>
    request<{ ok: boolean; day: string; pages_today: number }>(`/api/library/${id}/progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(location === undefined ? { pages } : { pages, location }),
    }),
  readingStats: (days = 30) => request<ReadingStats>(`/api/reading/stats?days=${days}`),
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
    const body: unknown = readJsonBody(text, response.status)
    if (!response.ok) {
      throw new ApiError(errorMessage(body, response.status), response.status)
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

  /**
   * Local password auth (`app/auth/` owns the truth). The session rides an
   * HttpOnly SameSite=Lax cookie the browser sends itself on same-origin
   * calls -- no token ever touches JS, so there is nothing to store, leak,
   * or attach to a header here.
   */
  authMe: () => request<AuthMeResponse>('/api/auth/me'),
  authSignup: (body: { email: string; password: string; display_name: string }) =>
    request<AuthResponse>('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  authLogin: (body: { email: string; password: string }) =>
    request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  authLogout: () =>
    request<{ ok: boolean }>('/api/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }),
  authChangePassword: (body: { current_password: string; new_password: string }) =>
    request<AuthResponse>('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  authSessions: () => request<{ items: AuthSession[] }>('/api/auth/sessions'),
  authEvents: () => request<{ items: AuthEvent[] }>('/api/auth/events'),
  authRevokeSession: (body: { session_id: string }) =>
    request<{ ok: boolean }>('/api/auth/sessions/revoke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  authRevokeAll: () =>
    request<{ ok: boolean; closed: number }>('/api/auth/revoke-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }),
  authRequestEmailCode: (body: { email: string }) =>
    request<{ sent: boolean; channel: string }>('/api/auth/email-code/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  authVerifyEmailCode: (body: { email: string; code: string }) =>
    request<AuthResponse>('/api/auth/email-code/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  /**
   * Start Google/Apple login. The server answers `{auth_url, state}` as JSON
   * (never a redirect), so the caller sets `window.location.href` itself and
   * the OAuth callback — which sets the cookie and 302s to /library — runs
   * as a top-level navigation where cookies belong.
   */
  authOAuthStart: (provider: 'google' | 'apple') =>
    request<{ auth_url: string; state: string }>(`/api/auth/oauth/${provider}/start`),
  /**
   * Which social providers are fully configured. The login page hides any
   * provider that is not — a button that can only fail is worse than none.
   */
  authOAuthStatus: () => request<{ google: boolean; apple: boolean }>('/api/auth/oauth/status'),

  /**
   * Ask the provider whether it is reachable, and whether the chosen model is in
   * its own list.
   *
   * This is the only way to turn "a key is present" into "translation will work".
   * Both fields are optional, so an empty body means "test what is saved".
   */
  testProvider: (body: { base_url?: string; api_key?: string; default_model?: string } = {}) =>
    request<ProviderTestResult>('/api/provider-config/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  /** Install a marketplace pack. Copies a glossary into this install. */
  installMarketplaceItem: (itemId: string) =>
    request<{ ok: boolean; id: string }>(
      `/api/account/marketplace/${encodeURIComponent(itemId)}/install`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
    ),

  /** Revoke an API key. The row stays, so the history is auditable. */
  revokeApiKey: (id: number) =>
    request<{ ok: boolean }>(`/api/account/api-keys/${id}/revoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }),

  /**
   * Store an uploaded book without translating it, and return where it landed.
   *
   * Storing is separate from starting: `POST /api/jobs` uploads *and* starts a
   * worker thread in the same request, so there was no moment at which the
   * browser held a file the server had not already begun paying to translate.
   * The calibration workshop needs exactly that moment.
   */
  uploadBook: async (file: File): Promise<UploadedBook> => {
    const form = new FormData()
    form.set('book', file, file.name)
    const response = await fetch('/api/jobs/upload', { method: 'POST', body: form })
    const text = await response.text()
    const body: unknown = readJsonBody(text, response.status)
    if (!response.ok) {
      throw new ApiError(errorMessage(body, response.status), response.status)
    }
    return withUploadId(body as UploadedBook)
  },

  /**
   * Import a rescue archive and put the book back into a resumable state.
   *
   * `POST /api/jobs/{id}/rescue` has always produced a portable archive of a job's
   * state. There was no route that read one, so a rescue could be downloaded and
   * never used -- a backup nobody could act on. This is the way back in.
   *
   * The archive carries its own settings, so the languages, the model and the
   * glossary come from it rather than from the form. The job lands `paused`, not
   * queued: the caller is expected to show the estimate for the *remaining* chunks
   * and then resume, so nothing is spent before it is priced.
   *
   * `force` is the answer to "this book is already on the server -- replace it?",
   * not a default. The first call omits it and gets a 409 describing what differs.
   */
  importRescue: async (
    file: File,
    options?: { /** `undefined` is "not specified", which is the first call. */
      force?: boolean | undefined },
  ) => {
    const form = new FormData()
    form.set('file', file, file.name)
    if (options?.force) form.set('force', 'true')
    const response = await fetch('/api/jobs/rescue/import', { method: 'POST', body: form })
    const text = await response.text()
    const body: unknown = readJsonBody(text, response.status)

    if (response.status === 409 && body && typeof body === 'object' && 'conflict' in body) {
      throw new RescueConflictError(
        (body as { error?: string }).error ?? 'این کتاب از قبل روی سرور هست.',
        (body as { conflict: RescueConflict }).conflict,
      )
    }
    if (!response.ok) {
      throw new ApiError(errorMessage(body, response.status), response.status)
    }
    return body as RescueImport
  },

  /**
   * Continue a job that was imported, paused, or stopped.
   *
   * A separate call from `importRescue` on purpose: the import stages the book and
   * the estimate dialog prices what is left, and only then is anything sent.
   */
  resumeJob: (id: string) => request<{ ok: true }>(`/api/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' }),

  /**
   * Estimate a translation run before it starts.
   *
   * Chunking the file to answer this is not free -- it reads the whole book and
   * runs the real chunker -- so the dialog is opened on the assumption the user
   * wants to translate, not on every keystroke.
   */
  estimate: (body: EstimateRequest) =>
    request<TranslationEstimate>('/api/jobs/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
