/* `.ts` on the specifier, like `chunks.ts` does for `./terms.ts`.

   This module is loaded by `node --test`, which strips types but does no path
   resolution of its own: an extensionless `./api` resolves under Vite and under
   `tsc`, and fails under the test runner with ERR_MODULE_NOT_FOUND — so the
   whole file, and the decisions in it, would be untestable. */
import { request } from './api.ts'

export type ToneId = 'modern' | 'literary' | 'academic' | 'faithful'
export interface TextSlot { id: string; text: string }
export interface CalibrationTerm {
  id: string; source_term: string; target_term: string; kind: string
  notes: string; approved: boolean; locked: boolean; evidence_id: string
}
export interface SampleResult {
  translations: TextSlot[]; plain: string; model: string
  origin: 'model' | 'human_edit' | 'protected'; reused: boolean; created_at?: string
}
export interface CalibrationSample {
  id: string; chapter: string; role: string; source: string; slots: TextSlot[]
  result: SampleResult | null; final_verified: boolean; approved: boolean
}
export interface CalibrationBudget {
  sample_tokens: number; total_tokens: number; max_calls: number; max_cost_micros: number | null
}
export interface CalibrationQuote {
  id: string; plan_hash: string; pricing: 'configured' | 'estimated' | 'unknown'
  input_tokens: number; output_tokens: number; reusable_units: number
  remaining_cost_low: number | null; remaining_cost_high: number | null
  sample_cost: number | null; spent_cost: number; reserved_cost: number
  spent_tokens: number; sample_spent_tokens: number; reserved_tokens: number; sample_calls: number
  token_method: string
}
export interface Calibration {
  id: string; revision: number; state: string; filename: string; busy: string | null; job_id: string | null
  approved_profile_hash: string | null; unit_count: number; warnings: string[]
  profile: { tone: ToneId; from_lang: string; to_lang: string; model: string; final_model: string; instructions: string; glossary: CalibrationTerm[] }
  samples: CalibrationSample[]
  candidates: { id: string; chapter: string; role: string; excerpt: string }[]
  tones: { id: ToneId; label: string; description: string }[]
  budget: CalibrationBudget; quote: CalibrationQuote
}
export interface CalibrationOperation {
  id: string; session_id: string; action: string; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  completed: number; total: number; error: string | null
}
export interface CalibrationPatch {
  tone?: ToneId; model?: string; final_model?: string; instructions?: string
  selected?: string[]; glossary?: CalibrationTerm[]; unlock_ids?: string[]; budget?: CalibrationBudget
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
const base = (id: string) => `/api/calibrations/${encodeURIComponent(id)}`

export const calibrationApi = {
  /**
   * Open a workshop on a stored upload.
   *
   * `tone` is optional on purpose: the server falls back to `literary`, and the
   * tone is chosen on real samples in the workshop anyway — sending it from the
   * upload form would mean deciding before seeing any of the book, and the
   * form's four presets (`literary`, `technical`, `conversational`, `formal`)
   * are not the workshop's four voices (`modern`, `literary`, `academic`,
   * `faithful`) at all, so a value from that list would be rejected.
   */
  create: (body: { upload_id: string; model: string; from_lang: string; to_lang: string; tone?: string; outputs: string[] }) =>
    request<Calibration>('/api/calibrations', json('POST', body)),
  list: () => request<{ items: { id: string; filename: string; state: string; updated_at: string }[] }>('/api/calibrations'),
  get: (id: string) => request<Calibration>(base(id)),
  edit: (s: Calibration, patch: CalibrationPatch) => request<Calibration>(base(s.id), json('PUT', { revision: s.revision, ...patch })),
  operation: (id: string) => request<CalibrationOperation>(`/api/calibration-operations/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<CalibrationOperation>(`/api/calibration-operations/${encodeURIComponent(id)}/cancel`, json('POST', {})),
  generate: (s: Calibration, sampleIds: string[], final = true) => request<CalibrationOperation>(`${base(s.id)}/generate`, {
    ...json('POST', { revision: s.revision, sample_ids: sampleIds, final }),
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
  }),
  propose: (s: Calibration) => request<CalibrationOperation>(`${base(s.id)}/propose`, {
    ...json('POST', { revision: s.revision }),
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
  }),
  feedback: (s: Calibration, sampleId: string, translations: TextSlot[]) =>
    request<Calibration>(`${base(s.id)}/feedback`, json('POST', { revision: s.revision, sample_id: sampleId, translations })),
  approveSample: (s: Calibration, sampleId: string) =>
    request<Calibration>(`${base(s.id)}/approve-sample`, json('POST', { revision: s.revision, sample_id: sampleId })),
  approve: (s: Calibration) => request<Calibration>(`${base(s.id)}/approve`, json('POST', { revision: s.revision })),
  start: (s: Calibration) => request<{ id: string }>(`${base(s.id)}/start`, json('POST', { revision: s.revision, quote_id: s.quote.id })),
}

/**
 * The workshop's state, in Persian.
 *
 * The server speaks SCREAMING_SNAKE (`AWAITING_USER_CALIBRATION`), which is
 * right for a machine and wrong for a list a person reads: it is 24 characters
 * of Latin on a card that also holds a Persian filename, and the badge ends up
 * wider than the book.
 *
 * Unknown states fall through to the raw value rather than to nothing — a new
 * state should read as unfamiliar, not as blank.
 */
const STATE_FA: Record<string, string> = {
  AWAITING_USER_CALIBRATION: 'در انتظار بازبینی',
  CALIBRATED_AND_ESTIMATED: 'آمادهٔ شروع',
  FULL_PROCESSING: 'در حال ترجمهٔ کتاب',
  COMPLETED: 'تکمیل‌شده',
  FAILED: 'ناموفق',
  CANCELLED: 'لغوشده',
  PAUSED: 'متوقف‌شده',
}

export function stateLabel(state: string): string {
  return STATE_FA[state] ?? state
}

export function canSeal(s: Calibration): boolean {
  return !s.busy && !s.job_id && s.samples.length > 0 && s.samples.every(sample => sample.approved && sample.final_verified)
}

/**
 * Swap one selected sample for another, without changing the order.
 *
 * Replaced rather than appended, because the server caps the set at three and
 * rejects a duplicate (`1 <= len(ids) <= 3` and `len(set(ids)) == len(ids)`).
 * The dropdown in `CalibrationPage` already hides samples that are selected, so
 * a collision cannot be chosen — but the set is made unique here as well, so
 * that one caller forgetting that filter is a duplicate on screen rather than a
 * 422 from the server.
 */
export function replaceSample(s: Calibration, previous: string, next: string): string[] {
  return [...new Set(s.samples.map((sample) => (sample.id === previous ? next : sample.id)))]
}

export function formatCost(value: number | null): string {
  if (value === null) return 'نامشخص'
  return `${new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 5 }).format(value)} دلار`
}
