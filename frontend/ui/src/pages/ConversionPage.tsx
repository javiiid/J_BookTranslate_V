import { useRef, useState } from 'react'
import { useConversion } from '@/hooks/useConversion'
import { CONVERSION_ACCEPT, CONVERSION_FORMATS, conversionFormatLabel } from '@/lib/conversion'
import { fa, faBytes } from '@/lib/format'
import './conversion.css'

export function ConversionPage() {
  const { file, outputs, pending, error, entries, selectFiles, clearFile, toggleOutput, start } = useConversion()
  const [view, setView] = useState<'new' | 'history'>('new')
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const latest = entries[0]
  const visibleEntries = view === 'history' ? entries : entries.slice(0, 1)

  return (
    <main className="conversion-page page" dir="rtl">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="conversion-eyebrow">ابزارهای سند</p>
          <h1 className="text-[length:var(--text-h1)] font-extrabold">تبدیل فایل</h1>
          <p className="conversion-muted mt-2">یک فایل، چند خروجی؛ آماده برای مطالعه، ویرایش و استفاده دوباره.</p>
        </div>
        <span className="badge badge-info">بدون ترجمه و مصرف مدل هوش مصنوعی</span>
      </header>

      <div className="conversion-switch mb-6" aria-label="نمایش بخش تبدیل">
        <button type="button" aria-pressed={view === 'new'} onClick={() => setView('new')}>تبدیل جدید</button>
        <button type="button" aria-pressed={view === 'history'} onClick={() => setView('history')}>
          عملیات این نشست <span className="conversion-count">{fa(entries.length)}</span>
          {pending && <span className="conversion-muted"> · در حال تبدیل</span>}
        </button>
      </div>

      {view === 'new' && (
        <form onSubmit={(event) => { event.preventDefault(); void start() }} className="conversion-layout">
          <div className="grid gap-5 min-w-0">
            <section className="surface-card p-5" aria-labelledby="conversion-upload-title">
              <h2 id="conversion-upload-title" className="conversion-section-title"><span className="conversion-step">۱</span> انتخاب فایل</h2>
              <div
                className="conversion-drop mt-5"
                data-dragging={dragging && !pending}
                onDragOver={(event) => { event.preventDefault(); if (!pending) setDragging(true) }}
                onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false) }}
                onDrop={(event) => { event.preventDefault(); setDragging(false); selectFiles(Array.from(event.dataTransfer.files)) }}
              >
                <span className="conversion-file-icon" aria-hidden="true">⇄</span>
                <strong className="block mt-3">فایل را اینجا رها کنید</strong>
                <p className="conversion-muted mt-1">یا از فایل‌های دستگاه خود انتخاب کنید</p>
                <button type="button" className="btn btn-secondary mt-4" disabled={pending} onClick={() => input.current?.click()}>
                  {file ? 'انتخاب فایل دیگر' : 'انتخاب فایل'}
                </button>
                <input ref={input} type="file" className="sr-only" tabIndex={-1} aria-label="انتخاب فایل برای تبدیل" accept={CONVERSION_ACCEPT} disabled={pending}
                  onChange={(event) => { selectFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
                <p className="conversion-muted mt-4"><bdi>EPUB · PDF · SRT · TXT · MD</bdi></p>
                <p className="conversion-muted mt-1">یک فایل در هر عملیات · حداکثر ۱۰۲۳ مگابایت</p>
              </div>
              {file && (
                <div className="conversion-selected mt-4">
                  <span className="conversion-step" aria-hidden="true">✓</span>
                  <div className="min-w-0 flex-1"><strong className="block break-all"><bdi>{file.name}</bdi></strong><span className="conversion-muted">{faBytes(file.size)} · آماده تبدیل</span></div>
                  <button type="button" className="btn btn-ghost" disabled={pending} onClick={clearFile}>حذف</button>
                </div>
              )}
            </section>

            <section className="surface-card p-5" aria-labelledby="conversion-output-title">
              <h2 id="conversion-output-title" className="conversion-section-title"><span className="conversion-step">۲</span> انتخاب خروجی</h2>
              <p className="conversion-muted mt-2">می‌توانید از همین فایل، چند خروجی هم‌زمان دریافت کنید.</p>
              <fieldset disabled={pending} className="conversion-formats mt-5">
                <legend className="sr-only">فرمت‌های خروجی</legend>
                {CONVERSION_FORMATS.map((format) => (
                  <label key={format.id} className="conversion-format" data-selected={outputs.includes(format.id)}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="conversion-extension">{format.extension}</span>
                      <input type="checkbox" checked={outputs.includes(format.id)} onChange={() => toggleOutput(format.id)} />
                    </div>
                    <strong className="block mt-3">{format.label}</strong>
                    <span className="conversion-muted block mt-1">{format.description}</span>
                  </label>
                ))}
              </fieldset>
              {outputs.includes('txt_bilingual') && <p className="alert alert-info mt-4">خروجی TXT موتور فعلی، متن اصلی را در دو بخش متن و ترجمه تکرار می‌کند؛ ترجمه جدیدی انجام نمی‌شود.</p>}
            </section>
          </div>

          <aside className="conversion-summary surface-card p-5">
            <h2 className="conversion-section-title"><span className="conversion-step">۳</span> شروع تبدیل</h2>
            <dl className="conversion-details mt-5">
              <div><dt>فایل ورودی</dt><dd className="break-all">{file ? <bdi>{file.name}</bdi> : 'انتخاب نشده'}</dd></div>
              <div><dt>حجم فایل</dt><dd>{file ? faBytes(file.size) : '—'}</dd></div>
              <div><dt>تعداد خروجی</dt><dd>{fa(outputs.length)} فرمت</dd></div>
            </dl>
            <div className="flex flex-wrap gap-2 mt-4">{outputs.map((output) => <span key={output} className="badge badge-info">{conversionFormatLabel(output)}</span>)}</div>
            <button type="submit" className="btn btn-primary w-full mt-6" disabled={pending || !file || !outputs.length}>
              {pending ? 'در حال ارسال و تبدیل…' : 'شروع تبدیل'}
            </button>
            <p className="conversion-muted mt-3">فایل روی سرور فعلی برنامه پردازش می‌شود. برای این عملیات به کلید مدل نیاز ندارید.</p>
            <div className="conversion-notes mt-5">
              <strong>پیش از شروع</strong>
              <ul className="list-disc ps-5 mt-2 space-y-2">
                <li>در تبدیل EPUB به Word و PDF، ساختار سند و تصاویر حفظ می‌شوند؛ صفحه‌بندی و فونت ممکن است با کتاب‌خوان متفاوت باشد.</li>
                <li>تبدیل PDF به Word همچنان بر پایه استخراج متن است و چیدمان اصلی را بازسازی نمی‌کند.</li>
                <li>PDF اسکن‌شده به OCR نیاز دارد؛ OCR در این نسخه فعال نیست.</li>
                <li>تا دریافت نتیجه، این زبانه را نبندید و صفحه را بازآوری نکنید. جابه‌جایی در منوی برنامه مجاز است.</li>
              </ul>
            </div>
          </aside>
        </form>
      )}

      {error && view === 'new' && <p role="alert" className="alert alert-error mt-5">{error}</p>}
      <section className="mt-6" aria-labelledby="conversion-results-title" aria-live="polite" aria-busy={pending}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 id="conversion-results-title" className="conversion-section-title">{view === 'history' ? 'عملیات این نشست' : 'نتیجه تبدیل'}</h2>
          {view === 'new' && entries.length > 1 && <button type="button" className="btn btn-ghost" onClick={() => setView('history')}>مشاهده همه عملیات</button>}
        </div>
        {view === 'history' && <p className="conversion-muted mb-4">این فهرست فقط تا زمان بازآوری یا بستن این زبانه نگهداری می‌شود. خروجی‌های موردنیاز را دریافت کنید.</p>}
        {!visibleEntries.length ? (
          <div className="surface-card p-8 text-center"><span className="conversion-file-icon" aria-hidden="true">↓</span><p className="font-semibold mt-3">{view === 'history' ? 'هنوز عملیاتی ثبت نشده است' : 'خروجی شما اینجا آماده دریافت می‌شود'}</p><p className="conversion-muted mt-2">یک فایل انتخاب کنید و فرمت‌های موردنیازتان را مشخص کنید.</p></div>
        ) : (
          <div className="grid gap-4">
            {visibleEntries.map((entry) => {
              const missing = entry.result ? entry.outputs.filter((output) => !entry.result?.versions.some((version) => version.name === output)) : []
              return (
                <article key={entry.key} className="surface-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0"><h3 className="font-semibold break-all"><bdi>{entry.filename}</bdi></h3><p className="conversion-muted mt-1">{new Date(entry.createdAt).toLocaleString('fa-IR')} · {entry.outputs.map(conversionFormatLabel).join('، ')}</p></div>
                    <span className={`badge ${entry.error ? 'badge-error' : !entry.result ? 'badge-info' : missing.length ? 'badge-warning' : 'badge-success'}`}>
                      {entry.error ? 'ناموفق' : !entry.result ? 'در حال ارسال و تبدیل' : missing.length ? 'خروجی ناقص' : 'آماده دریافت'}
                    </span>
                  </div>
                  {!entry.result && !entry.error && <p className="alert alert-info mt-4">فایل در حال ارسال یا پردازش است. سرویس درصد پیشرفت ارائه نمی‌کند؛ دریافت نتیجه ممکن است چند دقیقه طول بکشد.</p>}
                  {entry.error && <p className="alert alert-error mt-4">{entry.error}</p>}
                  {missing.length > 0 && <p className="alert alert-warning mt-4">این خروجی‌ها تولید نشدند: {missing.map(conversionFormatLabel).join('، ')}. نصب موتور خروجی و محتوای فایل را بررسی کنید.</p>}
                  {entry.result && <div className="flex flex-wrap gap-3 mt-4">{entry.result.versions.map((version) => <a key={version.name} href={version.download} download={version.filename} className="btn btn-secondary">↓ دریافت {conversionFormatLabel(version.name)}</a>)}</div>}
                  {entry === latest && entry.error && view === 'history' && <button type="button" className="btn btn-secondary mt-4" onClick={() => setView('new')}>بازگشت به تنظیمات</button>}
                </article>
              )
            })}
          </div>
        )}
      </section>

      <details className="conversion-help surface-card p-5 mt-6">
        <summary className="font-semibold cursor-pointer">چه فایل‌هایی را می‌توانم تبدیل کنم؟</summary>
        <div className="conversion-muted mt-4 space-y-3">
          <p>ورودی‌های فعلی EPUB، PDF متنی، زیرنویس SRT، متن TXT و Markdown هستند. EPUB برای خروجی Word، PDF و Markdown مستقیماً پردازش می‌شود تا تیترها، پاراگراف‌ها، جدول‌ها و تصاویر از مسیر متن ساده عبور نکنند.</p>
          <p>تصاویر خروجی Markdown داخل همان فایل قرار می‌گیرند؛ نمایش آن‌ها به پشتیبانی ویرایشگر شما از تصاویر تعبیه‌شده بستگی دارد. تبدیل PDF به Word ساختار صفحه اصلی را حفظ نمی‌کند.</p>
          <p>پشتیبانی از Word و PDF به نصب موتورهای مربوط روی سرور بستگی دارد؛ خروجی‌های تولیدنشده جداگانه مشخص می‌شوند. خروجی را پیش از استفاده نهایی بررسی کنید.</p>
          <p>تبدیل گروهی، OCR، خروجی EPUB، انتخاب بازه صفحات و تاریخچه دائمی در این نسخه ارائه نمی‌شوند.</p>
        </div>
      </details>
    </main>
  )
}
