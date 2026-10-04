import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { calibrationApi, stateLabel } from '@/lib/calibration'
import { EstimateModal } from '@/components/estimate/EstimateModal'
import {
  RescueConflictError,
  api,
  type RescueConflict,
  type RescueImport,
} from '@/lib/api'
import { fa, faDate } from '@/lib/format'

/**
 * Intake. Get a book into the calibration workshop, or bring work back.
 *
 * ## Why choosing a file does not start a translation
 *
 * This page used to end at `POST /api/jobs`, which uploads *and* starts a
 * worker thread in the same request -- so picking a file began spending money
 * immediately, and the glossary was something that appeared afterwards.
 *
 * Now a book goes to `/api/calibrations` instead. The server cuts it into a few
 * samples, the reader settles the voice and the glossary on those first, and
 * the full run starts from there with the profile locked. Uploading costs
 * nothing, and the wording says so, because now that is true.
 *
 * The rescue path is the exception and stays here: a rescue archive is already
 * translated work being restored, so it is priced through the estimate dialog
 * and then resumed.
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
  const [outputs, setOutputs] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const [notice, setNotice] = useState<{ text: string; tone: 'ok' | 'warn' | 'error' } | null>(null)

  const models = useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: 60_000 })
  const languages = useQuery({ queryKey: ['languages'], queryFn: api.languages, staleTime: 300_000 })
  const config = useQuery({ queryKey: ['provider-config'], queryFn: api.providerConfig, staleTime: 60_000 })

  // An empty choice means "use the configured default", so the form does not
  // need to know which model that is.
  const effectiveModel = model || config.data?.default_model || ''

  /* The upload does not start a translation.

     `POST /api/calibrations` takes the stored upload and opens a workshop: the
     book is cut into samples, the reader settles the voice and the glossary on
     those, and only then does the full run start. So this page's whole job is
     to get a file into that workshop -- there is no queue here, and no job, and
     nothing is sent to the provider by choosing a file.

     The one exception is a rescue archive, which is already-translated work:
     it goes back through the estimate dialog and resumes, so that path still
     lives here. */
  const [uploaded, setUploaded] = useState<{ path: string; name: string } | null>(null)

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const stored = await api.uploadBook(file)
      return calibrationApi.create({
        upload_id: stored.upload_id,
        model: effectiveModel,
        from_lang: from,
        to_lang: to,
        outputs,
      })
    },
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: ['calibrations'] })
      if (fileInput.current) fileInput.current.value = ''
      navigate(`/calibrations/${result.id}`)
    },
    onError: (error) => {
      setNotice({
        text: error instanceof Error ? error.message : 'آماده‌سازی کارگاه ترجمه ناموفق بود.',
        tone: 'error',
      })
    },
  })

  /** Workshops already open, so a half-finished one is reachable again. */
  const drafts = useQuery({
    queryKey: ['calibrations'],
    queryFn: calibrationApi.list,
    staleTime: 5_000,
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

  const submit = (file: File | null | undefined) => {
    if (!file || upload.isPending || rescue.isPending) return
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

    if (!/\.(epub|pdf|txt)$/i.test(file.name)) {
      setNotice({
        text: 'فقط فایل EPUB، PDF، TXT یا نسخهٔ نجاتی (ZIP) پذیرفته می‌شود.',
        tone: 'error',
      })
      return
    }
    /* Store, then open the workshop. No job, no provider call, no cost: the
       reader chooses the voice on real samples before anything is translated. */
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

  /**
   * Formats the calibrated run can produce.
   *
   * Deliberately not the full output list from the Python form: the server
   * rejects `srt` and `quality_report` in a calibration session
   * (`CalibrationService.create`), because neither has a final text to write
   * until the run is done. Offering them here would be offering a 422.
   */
  const OUTPUTS = [
    ['json_segments', 'حافظهٔ ترجمه'],
    ['txt_bilingual', 'متن دوزبانه'],
    ['markdown', 'مارک‌داون'],
    ['docx', 'ورد'],
    ['translated_pdf', 'PDF'],
    ['bilingual_pdf', 'PDF دوزبانه'],
  ] as const

  // Inline, never a full-page replacement: an upload failure must not unmount
  // the form, the settings and the glossary panel the reader just filled in.
  const uploadError = upload.isError
    ? upload.error instanceof Error ? upload.error.message : 'آپلود ناموفق بود.'
    : null

  return (
    <main className="page" dir="rtl">
      <header className="mb-6">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">افزودن کتاب</h1>
        <p
          className="mt-1 text-[length:var(--text-small)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          کتاب را وارد کنید، نمونه‌ها و واژه‌نامه را بررسی کنید و سپس ترجمهٔ کامل را شروع کنید. بارگذاری هزینهٔ مدل ندارد.
        </p>
      </header>

      {/* `min-w-0` on BOTH grid items, and it is load-bearing on the outer pair.
          A grid item defaults to `min-width: auto`, which means it may not be
          smaller than its widest content. The workshop list carries real book
          filenames — one is 150 characters of "Robert C. Martin Series…" — so
          the inner column grew to its max-content and pushed the document to
          1,608px on a 390px phone: the whole page scrolled sideways and the
          selects measured 1,550px wide.

          `minmax(0,1fr)` on the outer track only bounds the TRACK; the item
          inside still refuses to shrink unless it is told it may. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid min-w-0 gap-4">
          {/* ---- drop zone ----
              `role="group"` with a label, not `role="button"`: the zone itself
              is not keyboard-operable (drag only), and the labelled file input
              inside is the keyboard path. A button role here would bury a
              native control inside a fake one. */}
          <div
            role="group"
            aria-label="انتخاب فایل کتاب"
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
              کتاب EPUB، PDF یا TXT؛ یا نسخهٔ نجاتی ZIP برای ادامهٔ ترجمه
            </span>
            <label className="btn btn-secondary mt-2">
              انتخاب از دستگاه
              <input
                ref={fileInput}
                type="file"
                accept=".epub,.pdf,.txt,.zip"
                disabled={upload.isPending || rescue.isPending}
                className="sr-only"
                onChange={(event) => submit(event.target.files?.[0])}
              />
            </label>
          </div>

          {uploadError ? (
            <p role="alert" className="alert alert-error">
              {uploadError}
            </p>
          ) : null}

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

          {upload.isPending ? (
            <p role="status" className="alert alert-info">
              در حال آماده‌سازی کارگاه ترجمه…
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
                <span className="label">مدل پیش‌نویس و ترجمه</span>
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
            </div>

            <p
              className="mt-4 text-[length:var(--text-caption)]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              لحن، مدل نهایی، واژه‌نامه و سقف هزینه در کارگاه انتخاب می‌شوند؛ آنجا
              روی نمونهٔ واقعی کتاب تصمیم می‌گیرید، نه پیش از دیدن متن.
            </p>

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

          {/* ---- workshops already open ----
              A workshop is where the decisions live, so a half-finished one
              has to be reachable from here. Dropping the file again would open a
              second session and lose the approvals already paid for. */}
          <section className="surface-card p-5" aria-labelledby="drafts-heading">
            <h2 id="drafts-heading" className="text-[length:var(--text-h3)] font-extrabold">
              کارگاه‌های باز
            </h2>
            {drafts.isPending ? (
              <div className="skeleton mt-3" style={{ height: 64 }} />
            ) : drafts.isError ? (
              <p role="alert" className="alert alert-error mt-3">
                فهرست کارگاه‌ها خوانده نشد.
              </p>
            ) : (drafts.data?.items.length ?? 0) === 0 ? (
              <p className="mt-2 text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
                هنوز کارگاهی باز نیست. یک کتاب انتخاب کنید.
              </p>
            ) : (
              /* `min-w-0` on the row as well as the text block: `truncate` needs a
                 parent that has been told it may shrink, and a grid item is not
                 told that by default. The state badge is `flex-none` so it keeps
                 its own width instead of being squeezed to an ellipsis. */
              <ul className="mt-3 grid min-w-0 gap-2">
                {drafts.data?.items.map((draft) => (
                  <li key={draft.id} className="min-w-0">
                    <Link
                      to={`/calibrations/${draft.id}`}
                      className="flex min-w-0 items-center justify-between gap-3 rounded-[var(--radius-control)] border p-[var(--spacing-3)] no-underline"
                      style={{ borderColor: 'var(--color-border)' }}
                    >
                      <span className="min-w-0">
                        {/* The name is data, not a label: a real filename runs to
                            150 characters, so the full path goes in `title` and
                            the visible line is bounded rather than reflowed into
                            a dozen lines.

                            `dir="ltr"` on THIS element, and not a `<bdi>` around
                            the text: `text-overflow: ellipsis` puts the cut at
                            the *containing block's* inline end, and the page is
                            RTL, so the visible half was the tail —
                            "...ructure and Design-Pearson Education _2017_" —
                            with the part that identifies the book gone. An
                            isolate reorders the text but leaves the ellipsis
                            where it was; only the direction of the truncating
                            box moves it. `text-right` keeps the name against
                            the badge it sits beside. */}
                        <strong
                          dir="ltr"
                          className="block truncate text-right text-[length:var(--text-body)]"
                          title={draft.filename}
                        >
                          {draft.filename}
                        </strong>
                        <small
                          className="block text-[length:var(--text-caption)]"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {faDate(draft.updated_at)}
                        </small>
                      </span>
                      <span className="badge flex-none">{stateLabel(draft.state)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {/* ---- what happens next ---- */}
        <aside className="surface-card h-fit min-w-0 p-5">
          <h2 className="text-[length:var(--text-h3)] font-extrabold">بعد از بارگذاری</h2>
          <ol className="mt-3 grid gap-3">
            {[
              ['نمونه‌های واقعی', 'کتاب به چند بخش نماینده برش می‌خورد و همین‌جا نشان داده می‌شود.'],
              ['صدا و واژه‌نامه', 'لحن را می‌خوانید و اصطلاح‌ها را خودتان تأیید یا اصلاح می‌کنید.'],
              ['قفل پروفایل', 'پس از تأیید، لحن و واژه‌نامه قفل می‌شوند و بخش‌های تأییدشده دوباره هزینه نمی‌شوند.'],
              ['ترجمهٔ کامل', 'کتاب با همان پروفایل قفل‌شده وارد صف می‌شود.'],
            ].map(([title, body], index) => (
              <li key={title} className="flex gap-[var(--spacing-3)]">
                <span
                  className="grid size-7 flex-none place-items-center rounded-full text-[length:var(--text-small)] font-extrabold tabular-nums"
                  style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
                  aria-hidden="true"
                >
                  {fa(index + 1)}
                </span>
                <span className="min-w-0">
                  <strong className="block text-[length:var(--text-label)]">{title}</strong>
                  <span
                    className="mt-[var(--spacing-1)] block text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    {body}
                  </span>
                </span>
              </li>
            ))}
          </ol>
          <p
            className="mt-4 text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            بارگذاری هیچ هزینه‌ای ندارد. اولین تماس با مدل، وقتی است که خودتان دکمهٔ
            ترجمهٔ یک نمونه را می‌زنید.
          </p>
        </aside>
      </div>

      {/* The estimate dialog is the RESCUE path now.
          A rescue carries an already-priced remainder: some chunks are done and
          the rest are not, and what resuming will cost is the question. A fresh
          upload has no such number -- its cost depends on the profile that does
          not exist yet -- so it goes to the workshop instead, which quotes it
          against real samples. */}
      <EstimateModal
        open={rescued !== null && uploaded !== null}
        onClose={() => {
          setUploaded(null)
          setRescued(null)
        }}
        filePath={uploaded?.path ?? ''}
        bookTitle={uploaded?.name ?? ''}
        request={{
          /* A rescue's own settings, not the form's. The estimate has to price
             the run the resume will actually make, and that is the rescued job's
             model and language pair. */
          model: rescued?.model || effectiveModel,
          mode: rescued?.mode === 'batch' ? 'batch' : 'fast',
          concurrency: config.data?.max_concurrency,
          glossary_auto: false,
          from_lang: rescued?.from_lang || from,
          to_lang: rescued?.to_lang || to,
        }}
        starting={finish.isPending}
        onStart={() => {
          setRescued(null)
          setUploaded(null)
          finish.mutate()
        }}
      />
    </main>
  )
}
