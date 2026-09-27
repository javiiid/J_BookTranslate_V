import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { GlossaryReview } from '@/components/glossary/GlossaryReview'
import { GlossaryPanel } from '@/components/glossary/GlossaryPanel'

/**
 * The translation form.
 *
 * Ported from the workspace in `app/web.py`. The behaviour that matters:
 *
 * - a book is dropped or picked, then queued
 * - the glossary is *proposed and reviewed before* the run, not learned during
 *   it, so the same terminology applies to every chunk including the first
 * - the response carries `book_id`, which is what the glossary flow needs; when
 *   it is null the library index failed and the panel says so rather than
 *   silently doing nothing
 */
export function WorkspacePage() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement | null>(null)

  const [from, setFrom] = useState('EN')
  const [to, setTo] = useState('FA')
  const [model, setModel] = useState('')
  const [mode, setMode] = useState('fast')
  const [style, setStyle] = useState('literary')
  const [outputs, setOutputs] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const [bookId, setBookId] = useState<number | null>(null)
  const [reviewing, setReviewing] = useState(false)
  const [notice, setNotice] = useState<{ text: string; tone: 'ok' | 'warn' | 'error' } | null>(null)

  const models = useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: 60_000 })
  const languages = useQuery({ queryKey: ['languages'], queryFn: api.languages, staleTime: 300_000 })
  const config = useQuery({ queryKey: ['provider-config'], queryFn: api.providerConfig, staleTime: 60_000 })

  // An empty choice means "use the configured default", so the form does not
  // need to know which model that is.
  const effectiveModel = model || config.data?.default_model || ''

  const queue = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.set('from_lang', from)
      form.set('to_lang', to)
      if (effectiveModel) form.set('model', effectiveModel)
      form.set('mode', mode)
      form.set('style_preset', style)
      if (outputs.length) form.set('outputs', outputs.join(','))
      // The glossary is reviewed before the run, so nothing is learned mid-book.
      form.set('auto_glossary', 'false')
      form.set('book', file, file.name)
      return api.createJob(form)
    },
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: ['jobs'] })
      if (result.book_id) {
        setBookId(result.book_id)
        setNotice({ text: 'کتاب به صف اضافه شد.', tone: 'ok' })
      } else {
        setBookId(null)
        setNotice({
          text: 'کتاب در کتابخانه ثبت نشد؛ برای ساخت واژه‌نامه از صفحهٔ کتابخانه اقدام کنید.',
          tone: 'warn',
        })
      }
      if (fileInput.current) fileInput.current.value = ''
      navigate(`/jobs/${result.id}`)
    },
    onError: (error) => {
      setNotice({
        text: error instanceof Error ? error.message : 'افزودن کتاب به صف ناموفق بود',
        tone: 'error',
      })
    },
  })

  const submit = (file: File | null | undefined) => {
    if (!file) return
    if (!/^[^.]+\.(epub|pdf)$/i.test(file.name)) {
      setNotice({ text: 'فقط فایل EPUB یا PDF پذیرفته می‌شود.', tone: 'error' })
      return
    }
    setNotice(null)
    queue.mutate(file)
  }

  const toggleOutput = (value: string) => {
    setOutputs((previous) =>
      previous.includes(value) ? previous.filter((item) => item !== value) : [...previous, value],
    )
  }

  const OUTPUTS = [
    ['json_segments', 'حافظهٔ ترجمه'],
    ['txt_bilingual', 'متن دوزبانه'],
    ['markdown', 'مارک‌داون'],
    ['docx', 'ورد'],
    ['translated_pdf', 'PDF'],
    ['bilingual_pdf', 'PDF دوزبانه'],
    ['srt', 'زیرنویس'],
    ['quality_report', 'گزارش QA'],
  ] as const

  return (
    <main className="py-8" dir="rtl">
      <header className="mb-6">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">افزودن کتاب</h1>
        <p
          className="mt-1 text-[length:var(--text-small)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          فایل EPUB یا PDF را رها کنید. چند کتاب هم‌زمان پردازش می‌شوند.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-4">
          {/* ---- drop zone ---- */}
          <div
            className="grid place-items-center rounded-[var(--radius-panel)] border-2 border-dashed p-10 text-center"
            style={{
              borderColor: dragging ? 'var(--color-primary)' : 'var(--color-border-strong)',
              background: dragging ? 'var(--color-primary-subtle)' : 'var(--color-surface)',
            }}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              submit(event.dataTransfer.files[0])
            }}
          >
            <span className="mb-2 text-2xl" aria-hidden="true">
              ⬓
            </span>
            <strong className="text-[length:var(--text-body)]">فایل را اینجا رها کنید</strong>
            <span
              className="mt-1 text-[length:var(--text-caption)]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              یا
            </span>
            <label className="btn btn-secondary mt-2">
              انتخاب از دستگاه
              <input
                ref={fileInput}
                type="file"
                accept=".epub,.pdf"
                className="sr-only"
                onChange={(event) => submit(event.target.files?.[0])}
              />
            </label>
          </div>

          {notice ? (
            <p
              role={notice.tone === 'error' ? 'alert' : 'status'}
              className={`alert ${notice.tone === 'ok' ? 'alert-info' : notice.tone === 'warn' ? 'alert-warning' : 'alert-error'}`}
            >
              {notice.text}
            </p>
          ) : null}

          {queue.isPending ? (
            <p role="status" className="alert alert-info">
              در حال افزودن به صف…
            </p>
          ) : null}

          {/* ---- settings ---- */}
          <section className="surface-card p-5" aria-labelledby="settings-heading">
            <h2 id="settings-heading" className="mb-4 text-[length:var(--text-h3)] font-extrabold">
              تنظیمات ترجمه
            </h2>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1">
                <span className="label">زبان مبدأ</span>
                <select className="field" value={from} onChange={(event) => setFrom(event.target.value)}>
                  {(languages.data?.items ?? []).map((language) => (
                    <option key={language.code} value={language.code}>
                      {language.name} ({language.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1">
                <span className="label">زبان مقصد</span>
                <select className="field" value={to} onChange={(event) => setTo(event.target.value)}>
                  {(languages.data?.items ?? []).map((language) => (
                    <option key={language.code} value={language.code}>
                      {language.name} ({language.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1">
                <span className="label">مدل</span>
                <select className="field" value={model} onChange={(event) => setModel(event.target.value)}>
                  {/* Empty means "the configured default", so the form does not
                      hardcode a model the way the Python form did. */}
                  <option value="">
                    پیش‌فرض {config.data?.default_model ?? '—'}
                  </option>
                  {(models.data?.items ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1">
                <span className="label">سبک ترجمه</span>
                <select className="field" value={style} onChange={(event) => setStyle(event.target.value)}>
                  <option value="literary">ادبی</option>
                  <option value="technical">فنی</option>
                  <option value="conversational">محادثه‌ای</option>
                  <option value="formal">رسمی</option>
                </select>
              </label>

              <label className="grid gap-1">
                <span className="label">حالت</span>
                <select className="field" value={mode} onChange={(event) => setMode(event.target.value)}>
                  <option value="fast">سریع</option>
                  <option value="batch">Batch</option>
                  <option value="resume">ادامه</option>
                </select>
              </label>
            </div>

            <fieldset className="mt-5">
              <legend className="label mb-2">خروجی‌های اضافه</legend>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {OUTPUTS.map(([value, label]) => (
                  <label key={value} className="flex items-center gap-2 text-[length:var(--text-label)]">
                    <input
                      type="checkbox"
                      checked={outputs.includes(value)}
                      onChange={() => toggleOutput(value)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
          </section>
        </div>

        {/* ---- glossary ---- */}
        <aside className="surface-card h-fit p-5">
          <GlossaryPanel
            bookId={bookId}
            from={from}
            to={to}
            model={effectiveModel}
            onPropose={() => setReviewing(true)}
          />
        </aside>
      </div>

      {reviewing && bookId !== null ? (
        <GlossaryReview
          bookId={bookId}
          from={from}
          to={to}
          onClose={() => setReviewing(false)}
          onApproved={(text) => {
            setReviewing(false)
            setNotice({ text, tone: 'ok' })
          }}
          onError={(text) => setNotice({ text, tone: 'error' })}
        />
      ) : null}
    </main>
  )
}
