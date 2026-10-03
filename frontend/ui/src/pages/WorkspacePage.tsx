import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { EstimateModal } from '@/components/estimate/EstimateModal'
import {
  RescueConflictError,
  api,
  type RescueConflict,
  type RescueImport,
} from '@/lib/api'
import { fa } from '@/lib/format'
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
/**
 * What differs between the rescue and the copy already on the server.
 *
 * Only the settings that actually differ are listed. The server sends all four,
 * and a book imported twice over produces four identical lines -- which reads as
 * "everything changed" when nothing did, and trains the reader to skim past the
 * lines that matter.
 */
function ConflictDifferences({ detail }: { detail: RescueConflict }) {
  const LABELS: Record<string, string> = {
    model: 'مدل',
    from_lang: 'زبان مبدأ',
    to_lang: 'زبان مقصد',
    mode: 'حالت',
  }
  const changed = Object.entries(detail.differences).filter(
    ([, pair]) => pair.rescue !== pair.server,
  )
  if (changed.length === 0) {
    return (
      <p className="mt-1 text-[length:var(--text-caption)]">
        تنظیمات یکسان‌اند. اگر نسخهٔ نجاتی تازه‌تر است، جایگزین کنید.
      </p>
    )
  }
  return (
    <ul className="mt-2 flex flex-col gap-0.5 text-[length:var(--text-caption)]">
      {changed.map(([key, pair]) => (
        <li key={key} className="flex items-baseline gap-2">
          <span className="min-w-16" style={{ color: 'var(--color-text-muted)' }}>
            {LABELS[key] ?? key}
          </span>
          <span>
            <s>{pair.rescue}</s> ← <strong>{pair.server}</strong>
          </span>
        </li>
      ))}
    </ul>
  )
}

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

  /* The estimate dialog needs a path the server already has, because the
     estimate endpoint reads a file from disk. `POST /api/jobs` uploads *and*
     starts a translation in one request, so the book is uploaded first through
     `/api/jobs/upload` and only started after the dialog is confirmed. */
  const [pending, setPending] = useState<File | null>(null)
  const [uploaded, setUploaded] = useState<{ path: string; name: string } | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadBook(file),
    onSuccess: (result, file) => {
      setUploaded({ path: result.file_path, name: file.name })
      setPending(file)
    },
  })

  /* A rescue archive, rather than a book.

     `POST /api/jobs/{id}/rescue` produces a zip holding the translated text, the
     chunk list and the settings. There was no way to read one back, so a rescue
     could be downloaded and never used. Dropping one here restores the book and
     its progress, and the same estimate dialog then prices only what is left --
     so the reader sees what resuming will cost before it costs anything.

     The archive's own settings win over the form. It was translated with them,
     and mixing translations from two models in one book produces a glossary
     nobody chose. */
  const [rescued, setRescued] = useState<RescueImport | null>(null)
  const [conflict, setConflict] = useState<{ file: File; detail: RescueConflict } | null>(null)

  const rescue = useMutation({
    mutationFn: (input: { file: File; force?: boolean }) => api.importRescue(input.file, { force: input.force }),
    onSuccess: (result, input) => {
      setConflict(null)
      setRescued(result)
      setUploaded({ path: result.file_path, name: result.filename })
      // The dialog is opened on the restored path, not on the archive: the
      // estimate endpoint reads a book off disk, and the archive is not one.
      setPending(null)
      setNotice({
        text: `نسخهٔ نجاتی وارد شد: ${fa(result.chunks_already_done)} بخش از ${fa(
          result.chunk_count_total,
        )} پیش‌تر ترجمه شده است.`,
        tone: 'ok',
      })
      void input
    },
    onError: (error, input) => {
      if (error instanceof RescueConflictError) {
        setConflict({ file: input.file, detail: error.conflict })
        return
      }
      setNotice({
        text: error instanceof Error ? error.message : 'وارد کردن نسخهٔ نجاتی ناموفق بود.',
        tone: 'error',
      })
    },
  })

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
    setNotice(null)
    setConflict(null)
    setRescued(null)

    /* A rescue archive goes down a different road: it is unpacked server-side and
       the book is already on disk when the estimate dialog opens, so there is no
       upload step to run first. */
    if (/\.zip$/i.test(file.name)) {
      rescue.mutate({ file })
      return
    }

    if (!/^[^.]+\.(epub|pdf)$/i.test(file.name)) {
      setNotice({
        text: 'فقط فایل EPUB، PDF یا نسخهٔ نجاتی (ZIP) پذیرفته می‌شود.',
        tone: 'error',
      })
      return
    }
    /* Upload first, translate second. The estimate dialog sits between them, so
       the cost and the duration are visible before anything is spent. Going
       straight to `queue.mutate` would start the run on the server the moment the
       file was chosen, which is the thing the dialog exists to prevent. */
    upload.mutate(file)
  }

  const finish = useMutation({
    mutationFn: () => {
      if (!rescued) return Promise.resolve(null)
      return api.resumeJob(rescued.id)
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['jobs'] })
      if (rescued) {
        navigate(`/jobs/${rescued.id}`)
        return
      }
    },
  })

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

  if (upload.isError) {
    return (
      <p role="alert" className="alert alert-error">
        {upload.error instanceof Error ? upload.error.message : 'آپلود ناموفق بود.'}
      </p>
    )
  }

  return (
    <main className="page" dir="rtl">
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
              کتاب EPUB یا PDF، یا یک نسخهٔ نجاتی برای ادامهٔ ترجمه
            </span>
            <label className="btn btn-secondary mt-2">
              انتخاب از دستگاه
              <input
                ref={fileInput}
                type="file"
                accept=".epub,.pdf,.zip"
                className="sr-only"
                onChange={(event) => submit(event.target.files?.[0])}
              />
            </label>
          </div>

          {/* ---- the conflict question ----

              A rescue carries the settings it ran with, so importing it over a
              book that is already queued would change that book's language pair,
              model or glossary without asking. A different model means a
              different bill, and translations from two models in one book
              produce a glossary nobody chose -- so the reader is asked, and is
              shown what differs rather than a bare "already exists". */}
          {conflict ? (
            <div className="alert alert-warning" role="alertdialog" aria-label="این کتاب از قبل روی سرور هست">
              <p className="font-bold">
                <span aria-hidden="true">⚠</span> این کتاب از قبل روی سرور هست
              </p>
              <p className="mt-1">
                روی سرور {fa(conflict.detail.progress.completed)} بخش از{' '}
                {fa(conflict.detail.progress.total)} ترجمه شده؛ نسخهٔ نجاتی{' '}
                {fa(conflict.detail.rescued.chunks_already_done)} بخش از{' '}
                {fa(conflict.detail.rescued.chunk_count_total)}.
              </p>
              <ConflictDifferences detail={conflict.detail} />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    if (conflict.file) rescue.mutate({ file: conflict.file, force: true })
                  }}
                >
                  از نسخهٔ نجاتی استفاده کن
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setConflict(null)}
                >
                  کار فعلی را نگه دار
                </button>
              </div>
            </div>
          ) : null}

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


      <EstimateModal
        open={(pending !== null || rescued !== null) && uploaded !== null}
        onClose={() => {
          setPending(null)
          setUploaded(null)
          setRescued(null)
        }}
        filePath={uploaded?.path ?? ''}
        bookTitle={uploaded?.name ?? ''}
        request={{
          /* A rescue's own settings, not the form's. The estimate has to price
             the run the resume will actually make, and that is the rescued job's
             model and language pair. Using the form's would quote a different
             bill than the one the reader is about to pay. */
          model: rescued?.model || effectiveModel,
          mode: (rescued?.mode === 'batch' ? 'batch' : mode === 'batch' ? 'batch' : 'fast'),
          concurrency: config.data?.max_concurrency,
          glossary_auto: false,
          from_lang: rescued?.from_lang || from,
          to_lang: rescued?.to_lang || to,
        }}
        starting={queue.isPending || finish.isPending}
        onStart={() => {
          if (rescued) {
            setRescued(null)
            setUploaded(null)
            finish.mutate()
            return
          }
          const file = pending
          setPending(null)
          setUploaded(null)
          if (file) queue.mutate(file)
        }}
      />
    </main>
  )
}
