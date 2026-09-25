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

export const BADGE_CLASS: Record<JobStatus, string> = {
  queued: 'bg-slate-100 text-slate-600 border-slate-200',
  running: 'bg-blue-50 text-blue-700 border-blue-200',
  stopping: 'bg-amber-50 text-amber-700 border-amber-200',
  paused: 'bg-orange-50 text-orange-700 border-orange-200',
  stopped: 'bg-orange-50 text-orange-700 border-orange-200',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
  cancelled: 'bg-slate-100 text-slate-600 border-slate-200',
}

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
