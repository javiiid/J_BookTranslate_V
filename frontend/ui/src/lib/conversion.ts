export const CONVERSION_FORMATS = [
  { id: 'docx', label: 'Word', extension: 'DOCX', description: 'برای ویرایش متن در ورد' },
  { id: 'translated_pdf', label: 'PDF', extension: 'PDF', description: 'برای مطالعه و چاپ متن' },
  { id: 'markdown', label: 'Markdown', extension: 'MD', description: 'برای ویرایشگرهای متنی' },
  { id: 'txt_bilingual', label: 'متن', extension: 'TXT', description: 'متن با ساختار جفت بخش‌ها' },
  { id: 'json_segments', label: 'دادهٔ ساختاریافته', extension: 'JSON', description: 'برای پردازش بخش‌های متن' },
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
    return 'این فرمت پشتیبانی نمی‌شود. فایل EPUB، PDF، SRT، TXT یا MD انتخاب کنید.'
  }
  if (file.size === 0) return 'فایل انتخاب‌شده خالی است.'
  if (file.size > CONVERSION_MAX_BYTES) return 'حجم فایل باید حداکثر ۱۰۲۳ مگابایت باشد.'
  return null
}

export function conversionFormatLabel(format: ConversionFormat): string {
  return CONVERSION_FORMATS.find((item) => item.id === format)?.label ?? format
}

export function parseConversionResult(value: unknown): ConversionResult {
  if (!value || typeof value !== 'object' || !('id' in value) ||
      typeof value.id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(value.id) ||
      !('versions' in value) || !Array.isArray(value.versions)) {
    throw new Error('پاسخ سرویس تبدیل معتبر نیست. وضعیت سرور را بررسی کنید.')
  }
  const id = value.id
  const versions = value.versions.map((item: unknown) => {
    if (!item || typeof item !== 'object' || !('name' in item) ||
        !CONVERSION_FORMATS.some((format) => format.id === item.name) ||
        !('filename' in item) || typeof item.filename !== 'string' ||
        !('download' in item) || item.download !== `/downloads/convert/${id}/${String(item.name)}`) {
      throw new Error('اطلاعات فایل خروجی معتبر نیست.')
    }
    return { name: item.name as ConversionFormat, filename: item.filename, download: String(item.download) }
  })
  if (versions.length === 0) {
    throw new Error('هیچ خروجی تولید نشد. فایل ممکن است فاقد متن قابل استخراج باشد یا موتور خروجی در دسترس نباشد.')
  }
  return { id, versions }
}

export function conversionForm(file: File, outputs: readonly ConversionFormat[]): FormData {
  const error = conversionFileError(file)
  if (error) throw new Error(error)
  if (!outputs.length) throw new Error('حداقل یک فرمت خروجی انتخاب کنید.')
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
    throw new Error('ارتباط با سرور قطع شد. نتیجه عملیات مشخص نیست؛ پیش از اجرای دوباره، اتصال را بررسی کنید.')
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new Error('پاسخ قابل خواندن از سرویس تبدیل دریافت نشد. اتصال به سرور پایتون را بررسی کنید.')
  }
  if (!response.ok) {
    const message = body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
      ? body.error : `تبدیل ناموفق بود (${response.status}).`
    throw new Error(message)
  }
  return parseConversionResult(body)
}
