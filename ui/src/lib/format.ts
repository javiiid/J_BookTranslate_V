import type { JobStatus } from './api'

/** Persian labels, matching the wording used by the current Python pages so the
 *  port does not silently change the language of the product. */
export const STATUS_FA: Record<JobStatus, string> = {
  queued: 'در صف',
  running: 'در حال ترجمه',
  stopping: 'در حال توقف',
  paused: 'متوقف‌شده',
  stopped: 'متوقف‌شده',
  completed: 'تکمیل‌شده',
  failed: 'خطادار',
  cancelled: 'لغوشده',
}

export const HEALTH_FA = {
  green: 'سالم',
  yellow: 'نیازمند توجه',
  red: 'دارای مشکل',
} as const

export const MODE_FA: Record<string, string> = {
  fast: 'سریع',
  batch: 'Batch',
  batchcheck: 'Batch + بازبینی',
  resumebatch: 'ادامهٔ Batch',
  pdfbilingual: 'PDF دوزبانه',
}

export const STYLE_FA: Record<string, string> = {
  literary: 'ادبی',
  technical: 'فنی',
  conversational: 'محادثه‌ای',
  formal: 'رسمی',
}

export const ASSET_FA: Record<string, string> = {
  main: 'فایل اصلی',
  json_segments: 'حافظهٔ ترجمه (JSON)',
  txt_bilingual: 'متن دوزبانه',
  markdown: 'مارک‌داون',
  docx: 'ورد (DOCX)',
  translated_pdf: 'PDF ترجمه‌شده',
  bilingual_pdf: 'PDF دوزبانه',
  translated_epub: 'EPUB ترجمه‌شده',
  srt: 'زیرنویس (SRT)',
  quality_report: 'گزارش کیفیت',
  qa_report: 'گزارش کیفیت',
}

/**
 * Status presentation.
 *
 * These used to be Tailwind colour classes (`bg-emerald-50 text-emerald-700`
 * and friends), which pinned the old blue/green palette into the markup and
 * meant a brand change required editing eight strings in six files. They are
 * now token-driven class names, so a palette change touches only tokens.css.
 *
 * Each entry is a `badge` variant plus a state dot, never colour alone: the
 * label beside it is what carries the meaning.
 */
export type BadgeTone = 'info' | 'warning' | 'error' | 'success' | 'neutral' | 'brand'

const TONE_CLASS: Record<BadgeTone, string> = {
  info: 'badge badge-info',
  warning: 'badge badge-warning',
  error: 'badge badge-error',
  success: 'badge badge-success',
  neutral: 'badge',
  brand: 'badge badge-accent',
}

export const BADGE_TONE: Record<JobStatus, BadgeTone> = {
  queued: 'neutral',
  running: 'brand',
  stopping: 'warning',
  paused: 'warning',
  stopped: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'neutral',
}

/** Kept as a function of the tone so callers never concatenate class names. */
export const badgeClass = (status: JobStatus): string => TONE_CLASS[BADGE_TONE[status]]

const faNumber = new Intl.NumberFormat('fa-IR')

export const fa = (value: number | null | undefined): string => faNumber.format(value ?? 0)

export const faBytes = (bytes: number | null | undefined): string => {
  if (!bytes) return '—'
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`
  return `${Math.round(bytes / 1024)} KB`
}

export const faDuration = (seconds: number | null | undefined): string => {
  if (!seconds) return '—'
  const minutes = Math.ceil(seconds / 60)
  return minutes < 60
    ? `${fa(minutes)} دقیقه`
    : `${fa(Math.floor(minutes / 60))} ساعت و ${fa(minutes % 60)} دقیقه`
}

export const faDate = (value: string | null | undefined): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('fa-IR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
