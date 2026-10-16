import { createElement, type ReactNode } from 'react'
import type { JobStatus } from './api'
import { getLocale, localeTag } from './locale.ts'

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

export const STATUS_EN: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Translating',
  stopping: 'Stopping',
  paused: 'Paused',
  stopped: 'Stopped',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export const HEALTH_FA = {
  green: 'سالم',
  yellow: 'نیازمند توجه',
  red: 'دارای مشکل',
} as const

export const HEALTH_EN = {
  green: 'Healthy',
  yellow: 'Needs attention',
  red: 'Has issues',
} as const

/** A health state in the active language, falling back to a dash. */
export function healthLabel(health: string): string {
  const table = (getLocale() === 'fa' ? HEALTH_FA : HEALTH_EN) as Record<string, string>
  return table[health] ?? '—'
}

export const MODE_FA: Record<string, string> = {
  fast: 'سریع',
  batch: 'Batch',
  batchcheck: 'Batch + بازبینی',
  resumebatch: 'ادامهٔ Batch',
  pdfbilingual: 'PDF دوزبانه',
}

export const MODE_EN: Record<string, string> = {
  fast: 'Fast',
  batch: 'Batch',
  batchcheck: 'Batch + review',
  resumebatch: 'Batch resume',
  pdfbilingual: 'Bilingual PDF',
}

/** A processing mode in the active language, falling back to the raw value. */
export function modeLabel(mode: string): string {
  const table = getLocale() === 'fa' ? MODE_FA : MODE_EN
  return table[mode] ?? mode
}

export const STYLE_FA: Record<string, string> = {
  literary: 'ادبی',
  technical: 'فنی',
  conversational: 'محادثه‌ای',
  formal: 'رسمی',
}

export const STYLE_EN: Record<string, string> = {
  literary: 'Literary',
  technical: 'Technical',
  conversational: 'Conversational',
  formal: 'Formal',
}

/** A style preset in the active language, falling back to the raw value. */
export function styleLabel(style: string): string {
  const table = getLocale() === 'fa' ? STYLE_FA : STYLE_EN
  return table[style] ?? style
}

export const ASSET_FA: Record<string, string> = {
  main: 'فایل اصلی',
  json_segments: 'حافظهٔ ترجمه (JSON)',
  txt_bilingual: 'متن دوزبانه',
  markdown: 'مارک‌داون',
  docx: 'ورد (DOCX)',
  translated_pdf: 'PDF ترجمه‌شده',
  mobile_pdf: 'PDF موبایل',
  bilingual_pdf: 'PDF دوزبانه',
  translated_epub: 'EPUB ترجمه‌شده',
  srt: 'زیرنویس (SRT، زمان‌بندی تخمینی)',
  quality_report: 'گزارش کیفیت',
  qa_report: 'گزارش کیفیت',
}

export const ASSET_EN: Record<string, string> = {
  main: 'Main file',
  json_segments: 'Translation memory (JSON)',
  txt_bilingual: 'Bilingual text',
  markdown: 'Markdown',
  docx: 'Word (DOCX)',
  translated_pdf: 'Translated PDF',
  mobile_pdf: 'Mobile PDF',
  bilingual_pdf: 'Bilingual PDF',
  translated_epub: 'Translated EPUB',
  srt: 'Subtitles (SRT, estimated timing)',
  quality_report: 'Quality report',
  qa_report: 'Quality report',
}

/** An output asset name in the active language, falling back to the raw key. */
export function assetLabel(name: string): string {
  const table = getLocale() === 'fa' ? ASSET_FA : ASSET_EN
  return table[name] ?? name
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

/** A job's status in the active language, falling back to the raw value from the API. */
export function statusLabel(status: string): string {
  const table = (getLocale() === 'fa' ? STATUS_FA : STATUS_EN) as Record<string, string>
  return table[status] ?? status
}

/**
 * Server text in the active language.
 *
 * Failure reasons are produced by `_friendly_error` in `app/web.py`, which
 * writes Persian. The strings below are quoted character-for-character from
 * there: an exact match renders English, anything else (dynamic text, a new
 * backend message, English already) passes through untouched rather than
 * being guessed at. When the backend gains a message, it appears in Persian
 * until its mirror is added here -- visible, never blank.
 *
 * The table also holds the one success message the provider test prints, for
 * the same reason: it is server text, and English mode must not show Persian.
 */
const SERVER_ERROR_EN: Record<string, string> = {
  'اتصال سرویس ترجمه برقرار است':
    'Translation service is connected.',
  'کلید یا Base URL سرویس ترجمه تنظیم نشده است. از پنل کاربری ← تنظیمات سرویس ترجمه آن را وارد کنید.':
    'Translation service key or Base URL is not set. Enter it under Account → Translation service settings.',
  'کلید Provider پذیرفته نشد (401). این کلید با API Keyهای حساب کاربری تفاوت دارد.':
    'The provider rejected the key (401). This key is different from the account API keys.',
  'سرویس دسترسی را رد کرد (403). اعتبار حساب، مجوز مدل یا Firewall را بررسی کنید.':
    'The service denied access (403). Check account credit, model permission, or firewall.',
  'Base URL یا مدل پیدا نشد (404). آدرس سازگار معمولاً باید به /v1 ختم شود.':
    'Base URL or model not found (404). A compatible address usually ends with /v1.',
  'سقف درخواست‌های API پر شده است؛ کمی بعد دوباره ادامه دهید.':
    'The API request limit is reached; resume again shortly.',
  'ویندوز دسترسی شبکهٔ برنامه را مسدود کرده است (WinError 10013). برنامه را در Firewall مجاز کنید.':
    'Windows blocked the app’s network access (WinError 10013). Allow the app in Firewall.',
  'پاسخ Provider بیش از حد طول کشید؛ اینترنت یا وضعیت سرویس را بررسی کنید.':
    'The provider response took too long; check the internet connection or service status.',
  'ارتباط با Provider برقرار نشد. اینترنت، Firewall و Base URL را بررسی کنید.':
    'Could not reach the provider. Check the internet connection, firewall, and Base URL.',
  'ترجمه متوقف شد. جزئیات فنی در لاگ در دسترس است.':
    'Translation stopped. Technical details are in the log.',
}

export function serverError(text: string): string {
  if (getLocale() !== 'en') return text
  return SERVER_ERROR_EN[text] ?? text
}

/** Kept as a function of the tone so callers never concatenate class names.
 *  Accepts a plain string: the backend may add a status the `JobStatus`
 *  union does not know yet, and that must render a neutral badge rather than
 *  an `undefined` class. */
export const badgeClass = (status: string): string => TONE_CLASS[BADGE_TONE[status as JobStatus] ?? 'neutral']

const faNumber = new Intl.NumberFormat('fa-IR')
const enNumber = new Intl.NumberFormat('en-US')

/** A count in the active language's digits. Defaults to Persian, which is
 *  what every existing caller and test expects until the toggle is used. */
export const fa = (value: number | null | undefined): string =>
  (getLocale() === 'fa' ? faNumber : enNumber).format(value ?? 0)

/**
 * A money amount, in dollars.
 *
 * `toFixed(2)` rather than `fa()`: a currency figure is conventionally written
 * with Latin digits and a decimal point even in Persian text, and `fa()` would
 * render it `۰٫۰۸`, which beside a "start translating" button no longer reads as
 * a price to compare against a provider's invoice.
 *
 * ## Why a sub-cent amount gets more digits
 *
 * Resuming a nearly-finished book bills only what is left. Four chunks of
 * `gemini-3.1-flash-lite` cost about $0.0024, which `toFixed(2)` prints as
 * `$0.00` -- and `$0.00` is the one string this whole feature was built to never
 * show. A zero beside a "start translating" button reads as free, and a reader
 * who has just watched the dialog distinguish a real zero from an unknown price
 * is exactly the reader who will read `$0.00` as free.
 *
 * So a non-zero amount below a cent is printed at four decimals. The server
 * already carries `base`, `translation` and `glossary` at that precision, so
 * nothing is invented here.
 */
export const usd = (value: number): string => {
  if (!Number.isFinite(value)) return '—'
  if (value !== 0 && Math.abs(value) < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

/**
 * Mark a string as needing left-to-right layout, inside right-to-left text.
 *
 * ## Why this exists
 *
 * The estimate dialog is RTL and the numbers in it are Latin. A Latin run next
 * to a neutral character in an RTL paragraph is reordered by the Unicode bidi
 * algorithm, which is correct and is not what a reader of a price wants.
 *
 * Measured with python-bidi, in an RTL paragraph:
 *
 * ```
 * logical  : "شامل واژه‌نامه +$0.12"
 * on screen: "0.12$+ همانهژاو لماش"
 * ```
 *
 * The `+` lands on the far side of the number from the `$`. Inside an LTR
 * isolate the same string stays `+$0.12`.
 *
 * The range `$0.15 – $0.20` needed no fix and got none in substance: reordered,
 * it reads right-to-left with the smaller number first, which is what a Persian
 * reader expects of a range. It is isolated anyway, because a price is not
 * somewhere to depend on which way the eye scans.
 *
 * ## Why it is an identity function
 *
 * The real work is the `<bdi>` in :func:`Ltr`. This is a marker for call sites
 * building a string -- it makes the intent legible and it means a template
 * literal cannot accidentally produce `[object Object]`.
 *
 * The first version returned a `ReactElement`, and a call site interpolated it
 * into a template string. That rendered:
 *
 * ```
 * <p>یک ترجمهٔ ناتمام پیدا شد — [object Object] از [object Object] بخش ذخیره شده است.</p>
 * ```
 *
 * The isolate was working perfectly, around the wrong content. Returning a
 * `string` makes that mistake impossible rather than merely discouraged.
 *
 * `createElement` rather than JSX below, and the parameter is `string` rather
 * than `string | number`, for the same reason: this file has to stay `.ts`. The
 * tests import it with `node --test`, which strips types but does not transform
 * JSX -- a `.tsx` here failed with `ERR_UNKNOWN_FILE_EXTENSION`, the whole test
 * file going down rather than one assertion.
 */
export const ltr = (value: string): string => value

/** Wrap a run in a left-to-right isolate. `<bdi>`, not a styled span: it is one
 *  attribute's worth of markup and it needs no CSS to be correct. */
export const Ltr = ({ children }: { children: ReactNode }) =>
  createElement('bdi', null, children)

export const faBytes = (bytes: number | null | undefined): string => {
  if (!bytes) return '—'
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`
  return `${Math.round(bytes / 1024)} KB`
}

export const faDuration = (seconds: number | null | undefined): string => {
  if (!seconds) return '—'
  const minutes = Math.ceil(seconds / 60)
  if (getLocale() !== 'fa') {
    return minutes < 60
      ? `${fa(minutes)} min`
      : `${fa(Math.floor(minutes / 60))} hr ${fa(minutes % 60)} min`
  }
  return minutes < 60
    ? `${fa(minutes)} دقیقه`
    : `${fa(Math.floor(minutes / 60))} ساعت و ${fa(minutes % 60)} دقیقه`
}

export const faDate = (value: string | null | undefined): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(localeTag(), {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/**
 * How long ago, in words: «لحظاتی پیش»، «۳ ساعت پیش»، «۲ روز پیش».
 *
 * For rows where the absolute date answers nothing ("this changed recently"
 * is the whole question). Beyond 30 days it falls back to `faDate`, because
 * "۴۷ روز پیش" is arithmetic homework and a date is the answer.
 *
 * A future stamp — clock skew between browser and server — reads as "just
 * now" rather than a negative duration, which would be a lie in the other
 * direction.
 */
export const faAgo = (value: string | null | undefined, now: number = Date.now()): string => {
  if (!value) return '—'
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return '—'
  const seconds = Math.max(0, Math.floor((now - then) / 1000))
  if (getLocale() !== 'fa') {
    if (seconds < 60) return 'just now'
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${fa(minutes)} min ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${fa(hours)} hr ago`
    const days = Math.floor(hours / 24)
    if (days < 30) return `${fa(days)} days ago`
    return faDate(value)
  }
  if (seconds < 60) return 'لحظاتی پیش'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${fa(minutes)} دقیقه پیش`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${fa(hours)} ساعت پیش`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${fa(days)} روز پیش`
  return faDate(value)
}

/**
 * Mask anything that is shaped like a provider secret.
 *
 * `/api/account/portal` returns each API key's `name` verbatim, and the server
 * stores whatever it was given in that column. In this installation the column
 * holds a string beginning with `sk-`, which is exactly the shape of a provider
 * key -- so rendering the name as-is would put a secret in the DOM, in the
 * page source, and in any screenshot.
 *
 * This is a client-side guard, not a fix. The right place to stop it is the
 * server, which should not echo a free-text column as if it were a label. But
 * the column is user data and the endpoint is fixed, so the page declines to
 * print anything that looks like a credential.
 *
 * The mask keeps the first few characters so a key can still be told apart from
 * its neighbours, which is the only reason to display it at all.
 */
export const maskSecretLike = (value: string | null | undefined): string => {
  const text = (value ?? '').trim()
  if (!text) return '—'
  // Provider keys in the wild start sk-, jbt_live_, or a long opaque token.
  //
  // The `sk-` pattern accepts four or more characters after the dash, not eight.
  // An earlier version required eight, which meant a short `sk-1234` was printed
  // in full -- the one input the reader is most likely to paste in to try it, and
  // the one most likely to be a real short-lived key.
  const looksSecret =
    /^sk-[A-Za-z0-9_-]{4,}$/.test(text) ||
    /^(jbt|pk|api)[_-]/i.test(text) ||
    (text.length >= 32 && /^[A-Za-z0-9_-]+$/.test(text))
  if (!looksSecret) return text
  if (text.length <= 8) return '••••'
  return `${text.slice(0, 4)}${'•'.repeat(Math.min(12, text.length - 4))}`
}
