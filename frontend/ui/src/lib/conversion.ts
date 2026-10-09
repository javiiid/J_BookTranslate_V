import { getLocale } from './locale.ts'

/** Persian default, English mirror: `getLocale()` decides at call time,
 *  so tests (which never toggle) keep seeing Persian without setup. */
function L(faText: string, enText: string): string {
  return getLocale() === 'fa' ? faText : enText
}

export const CONVERSION_FORMATS = [
  { id: 'docx', label: 'Word', labelEn: 'Word', extension: 'DOCX', description: 'برای ویرایش متن در ورد', descriptionEn: 'For editing text in Word' },
  { id: 'translated_pdf', label: 'PDF', labelEn: 'PDF', extension: 'PDF', description: 'برای مطالعه و چاپ متن', descriptionEn: 'For reading and printing' },
  { id: 'markdown', label: 'Markdown', labelEn: 'Markdown', extension: 'MD', description: 'برای ویرایشگرهای متنی', descriptionEn: 'For text editors' },
  { id: 'txt_bilingual', label: 'متن', labelEn: 'Text', extension: 'TXT', description: 'متن با ساختار جفت بخش‌ها', descriptionEn: 'Text with paired-section structure' },
  { id: 'json_segments', label: 'دادهٔ ساختاریافته', labelEn: 'Structured data', extension: 'JSON', description: 'برای پردازش بخش‌های متن', descriptionEn: 'For processing text sections' },
] as const

export type ConversionFormat = (typeof CONVERSION_FORMATS)[number]['id']

export interface ConversionResult {
  id: string
  versions: { name: ConversionFormat; download: string; filename: string }[]
}

export const CONVERSION_ACCEPT = '.epub,.pdf,.srt,.txt,.md'
export const CONVERSION_MAX_BYTES = 1024 * 1024 * 1024 - 1024 * 1024

export function conversionFileError(file: { name: string; size: number }): string | null {
  if (!/\.(epub|pdf|srt|txt|md)$/i.test(file.name)) {
    return L('این فرمت پشتیبانی نمی‌شود. فایل EPUB، PDF، SRT، TXT یا MD انتخاب کنید.', 'Unsupported format. Choose an EPUB, PDF, SRT, TXT or MD file.')
  }
  if (file.size === 0) return L('فایل انتخاب‌شده خالی است.', 'The chosen file is empty.')
  if (file.size > CONVERSION_MAX_BYTES) return L('حجم فایل باید حداکثر ۱۰۲۳ مگابایت باشد.', 'Files must be at most 1023 MB.')
  return null
}

export function conversionCountError(): string {
  return L('در هر عملیات یک فایل انتخاب کنید. می‌توانید چند فرمت خروجی بگیرید.', 'Choose one file per run. You may take several output formats.')
}

export function conversionSelectionError(): string {
  return L('یک فایل و حداقل یک فرمت خروجی انتخاب کنید.', 'Choose a file and at least one output format.')
}

export function conversionFailedError(): string {
  return L('تبدیل فایل ناموفق بود.', 'File conversion failed.')
}

export function conversionFormatLabel(format: ConversionFormat): string {
  const found = CONVERSION_FORMATS.find((item) => item.id === format)
  if (!found) return format
  return getLocale() === 'fa' ? found.label : found.labelEn
}

export function conversionFormatDescription(format: ConversionFormat): string {
  const found = CONVERSION_FORMATS.find((item) => item.id === format)
  if (!found) return ''
  return getLocale() === 'fa' ? found.description : found.descriptionEn
}

export function parseConversionResult(value: unknown): ConversionResult {
  if (!value || typeof value !== 'object' || !('id' in value) ||
      typeof value.id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(value.id) ||
      !('versions' in value) || !Array.isArray(value.versions)) {
    throw new Error(L('پاسخ سرویس تبدیل معتبر نیست. وضعیت سرور را بررسی کنید.', 'Invalid conversion service response. Check the server status.'))
  }
  const id = value.id
  const versions = value.versions.map((item: unknown) => {
    if (!item || typeof item !== 'object' || !('name' in item) ||
        !CONVERSION_FORMATS.some((format) => format.id === item.name) ||
        !('filename' in item) || typeof item.filename !== 'string' ||
        !('download' in item) || item.download !== `/downloads/convert/${id}/${String(item.name)}`) {
      throw new Error(L('اطلاعات فایل خروجی معتبر نیست.', 'Invalid output file info.'))
    }
    return { name: item.name as ConversionFormat, filename: item.filename, download: String(item.download) }
  })
  if (versions.length === 0) {
    throw new Error(L('هیچ خروجی تولید نشد. فایل ممکن است فاقد متن قابل استخراج باشد یا موتور خروجی در دسترس نباشد.', 'No outputs were produced. The file may lack extractable text or the output engine is unavailable.'))
  }
  return { id, versions }
}

export function conversionForm(file: File, outputs: readonly ConversionFormat[]): FormData {
  const error = conversionFileError(file)
  if (error) throw new Error(error)
  if (!outputs.length) throw new Error(L('حداقل یک فرمت خروجی انتخاب کنید.', 'Choose at least one output format.'))
  const form = new FormData()
  form.append('convert_book', file)
  for (const output of new Set(outputs)) form.append('convert_outputs', output)
  return form
}

export async function convertFile(file: File, outputs: readonly ConversionFormat[]): Promise<ConversionResult> {
  const form = conversionForm(file, outputs)
  let response: Response
  try {
    response = await fetch('/api/convert', { method: 'POST', body: form, headers: { Accept: 'application/json' } })
  } catch {
    throw new Error(L('ارتباط با سرور قطع شد. نتیجه عملیات مشخص نیست؛ پیش از اجرای دوباره، اتصال را بررسی کنید.', 'Lost connection to the server. The result is unknown; check the connection before retrying.'))
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new Error(L('پاسخ قابل خواندن از سرویس تبدیل دریافت نشد. اتصال به سرور پایتون را بررسی کنید.', 'No readable response from the conversion service. Check the Python server connection.'))
  }
  if (!response.ok) {
    const message = body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
      ? body.error : L(`تبدیل ناموفق بود (${response.status}).`, `Conversion failed (${response.status}).`)
    throw new Error(message)
  }
  return parseConversionResult(body)
}
