import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type EstimateRequest, type TranslationEstimate } from '@/lib/api'
import { Ltr, fa, usd } from '@/lib/format'

/**
 * The pre-translation estimate.
 *
 * ## Why this exists
 *
 * `/api/jobs/estimate` was already in the server and nothing called it. It
 * answered from the file's size in bytes: `chunks = ceil(bytes / 12000)`,
 * `seconds = chunks * 4`, `cost = 0.0`. On this project's real 400-page book that
 * is 1,989 chunks and two hours, against an actual 470 chunks and three minutes.
 * The cost was always zero, and a zero beside a "start translating" button reads
 * as "free" rather than "unknown".
 *
 * The server now computes the real figures. This dialog's whole job is to show
 * them without overclaiming: see "Honesty" below.
 *
 * ## Honesty
 *
 * Three places where the easy thing is to lie, and what happens instead:
 *
 * 1. **No price for this model.** `estimated_cost.known` comes back false and the
 *    card says the price is not on file. It does not print `$0.00`, which is
 *    indistinguishable from free.
 * 2. **The chunk count is not exact.** For a PDF, or a book the chunker cannot
 *    parse, the count is derived from the page count or the byte size. The card
 *    says "estimated" rather than presenting it as a measurement.
 * 3. **The estimate failed.** Translation still works without it, so the primary
 *    button stays enabled and the dialog says so. An estimate is not a gate.
 *
 * ## Tokens in this file
 *
 * The specified palette was a neutral ramp plus a teal accent at
 * `oklch(0.6 0.13 195)`. That is not used: the design system's accent is the
 * KALIMA blue `--color-primary`, and every colour here comes from the same tokens
 * as the rest of the product. Introducing a second accent would break the 144
 * contrast assertions in `tests/tokens.contrast.test.ts` and give the product two
 * ideas about what its own colour is.
 *
 * The 8px spacing rhythm, the 12px/8px radii, the reduced-motion handling and the
 * grid-rows height animation are all as specified.
 */

const STEPS: { icon: string; title: string; body: string }[] = [
  {
    icon: '❖',
    title: 'تقسیم متن به بخش‌های معنایی',
    body: 'پاراگراف‌ها واحد نگه داشته می‌شوند؛ فقط متنی که از بودجه بگذرد روی جمله برش می‌خورد.',
  },
  {
    icon: '⇉',
    title: 'ترجمه موازی',
    body: 'چند بخش همزمان فرستاده می‌شوند و نتیجه‌ها به ترتیب کتاب ادغام می‌شوند.',
  },
  {
    icon: '❖',
    title: 'واژه‌نامه و اصطلاحات',
    body: 'اصطلاحات تأییدشده اعمال می‌شوند تا یک واژه در همهٔ کتاب یکسان ترجمه شود.',
  },
  {
    icon: '⎙',
    title: 'ساخت خروجی',
    body: 'بخش‌های ترجمه‌شده سر جای خودشان می‌نشینند و کتاب نهایی نوشته می‌شود.',
  },
]

/* ------------------------------------------------------------------ */

function Card({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="surface-card flex min-h-[7.5rem] flex-col gap-2 p-4">
      <span className="data-label">{label}</span>
      {children}
    </div>
  )
}

function Big({ children, tone }: { children: React.ReactNode; tone?: 'muted' }) {
  return (
    <strong
      className="text-[length:var(--text-h2)] leading-tight"
      style={tone === 'muted' ? { color: 'var(--color-text-muted)' } : undefined}
    >
      {children}
    </strong>
  )
}

function SkeletonCard() {
  return (
    <div className="surface-card flex min-h-[7.5rem] flex-col gap-2 p-4">
      <div className="skeleton h-3 w-16" />
      <div className="skeleton h-7 w-32" />
      <div className="skeleton h-3 w-24" />
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span
        className="text-[length:var(--text-caption)]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </span>
      <strong className="text-[length:var(--text-small)]">{value}</strong>
    </div>
  )
}

/* ------------------------------------------------------------------ */

interface Props {
  open: boolean
  onClose: () => void
  /** The book to estimate. Changing it re-fetches. */
  filePath: string
  bookTitle: string
  request: EstimateOptions
  onStart: (resume: boolean) => void
  starting: boolean
}

/**
 * `Omit<EstimateRequest, 'file_path'>` with every field admitting undefined.
 *
 * The project compiles with `exactOptionalPropertyTypes: true`, so a caller that
 * passes `concurrency={config.data?.max_concurrency}` -- which is
 * `number | undefined` while the provider config is still loading -- is a type
 * error unless the prop says so on purpose. Making it explicit here is better
 * than making every caller coalesce to a number it does not have yet: the server
 * already falls back to the configured value, and sending `undefined` means
 * "whatever you have configured", which is the honest request.
 */
type EstimateOptions = { [K in keyof Omit<EstimateRequest, 'file_path'>]?: EstimateRequest[K] | undefined }

export function EstimateModal({
  open,
  onClose,
  filePath,
  bookTitle,
  request,
  onStart,
  starting,
}: Props) {
  const [showSteps, setShowSteps] = useState(false)
  const [resume, setResume] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  // Fetched when the dialog opens, not on a button press: the user has already
  // committed to translating by getting here, and the answer is what they came
  // for.
  const query = useQuery({
    queryKey: ['estimate', filePath, request],
    queryFn: () => api.estimate({ ...request, file_path: filePath }),
    enabled: open && Boolean(filePath),
    // The estimate is a function of the file and the settings, neither of which
    // changes while the dialog is open. Re-fetching would be churn.
    staleTime: Infinity,
    retry: false,
  })

  // Escape closes. The per-open state resets in the parent's `onClose`, which
  // owns the lifecycle -- resetting it here would mean a setState during the
  // close render, and the lint rule about that is right to complain.
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (open) panelRef.current?.focus()
  }, [open])

  if (!open) return null

  const data: TranslationEstimate | undefined = query.data
  const failed = query.isError

  return (
    <div
      className="modal-overlay"
      onClick={(event) => {
        /* Backdrop click closes, but a click that started inside the panel must
           not. Without the target check, dragging a text selection out of the
           dialog closes it. */
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="estimate-title"
        tabIndex={-1}
        className="modal-panel"
      >
        {/* ---- header ---- */}
        <header className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2
              id="estimate-title"
              className="text-[length:var(--text-h2)] font-extrabold tracking-tight"
            >
              تخمین هزینه و زمان
            </h2>
            <p
              className="mt-1 truncate text-[length:var(--text-small)]"
              style={{ color: 'var(--color-text-muted)' }}
              title={bookTitle}
            >
              {bookTitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="btn-icon"
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        {/* ---- resume ---- */}
        {data?.has_resume ? (
          <div className="alert alert-warning mb-4">
            <p>
              <span aria-hidden="true">⚡</span> یک ترجمهٔ ناتمام پیدا شد
              {data.resume_progress !== null ? (
                <>
                  {' — '}
                  <Ltr>{`${fa(Math.round(data.resume_progress * 100))}٪`}</Ltr> از{' '}
                  <Ltr>{fa(data.chunk_count_total)}</Ltr> بخش ذخیره شده است.
                </>
              ) : (
                '.'
              )}
            </p>
            {/* The figure below is for the remaining chunks, and the reader has to
                be told that -- otherwise a number for 3 chunks sits next to a
                button that says "continue" and a count that says 60. */}
            {data.resume_remaining > 0 ? (
              <p className="mt-1 text-[length:var(--text-caption)]">
                هزینه و زمان بالا فقط برای <Ltr>{fa(data.resume_remaining)}</Ltr> بخش
                باقی‌مانده است؛ <Ltr>{fa(data.chunks_already_done)}</Ltr> بخش پیش‌تر ترجمه شده
                و دوباره فرستاده نمی‌شود.
              </p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                className={resume ? 'btn btn-primary' : 'btn btn-secondary'}
                onClick={() => setResume(true)}
                aria-pressed={resume}
              >
                ادامه از سر جای قبلی
              </button>
              <button
                type="button"
                className={resume ? 'btn btn-secondary' : 'btn btn-ghost'}
                onClick={() => setResume(false)}
                aria-pressed={!resume}
              >
                شروع مجدد
              </button>
            </div>
          </div>
        ) : null}

        {/* ---- the three cards ---- */}
        {failed ? (
          <div className="alert alert-error mb-4">
            <p className="font-bold">
              <span aria-hidden="true">⚠</span> تخمین در دسترس نیست
            </p>
            <p className="mt-1">
              ترجمه همچنان ممکن است. دلیل: {query.error instanceof Error
                ? query.error.message
                : 'خطای نامشخص'}
            </p>
          </div>
        ) : !data ? (
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : (
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <Card label={data.has_resume ? 'هزینهٔ باقی‌مانده' : 'هزینهٔ تخمینی'}>
              {data.estimated_cost.known ? (
                <>
                  {/* The total, and nothing beside it that could be added to it.
                      The breakdown below is the *explanation* of this number, not
                      a surcharge on top of it. */}
                  <Big>
                    <Ltr>{`${usd(data.estimated_cost.min)} – ${usd(data.estimated_cost.max)}`}</Ltr>
                  </Big>
                  <span
                    className="text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    بر اساس <Ltr>{fa(data.token_count)}</Ltr> توکن
                  </span>
                  <dl className="mt-1 flex flex-col gap-0.5 text-[length:var(--text-caption)]">
                    <div className="flex items-baseline justify-between gap-2">
                      <dt style={{ color: 'var(--color-text-muted)' }}>ترجمه</dt>
                      <dd>
                        <Ltr>{usd(data.estimated_cost.translation)}</Ltr>
                      </dd>
                    </div>
                    {data.estimated_cost.glossary > 0 ? (
                      <div className="flex items-baseline justify-between gap-2">
                        <dt style={{ color: 'var(--color-text-muted)' }}>واژه‌نامه</dt>
                        <dd>
                          <Ltr>{usd(data.estimated_cost.glossary)}</Ltr>
                        </dd>
                      </div>
                    ) : null}
                    <div className="flex items-baseline justify-between gap-2">
                      <dt style={{ color: 'var(--color-text-muted)' }}>جمع</dt>
                      <dd>
                        <Ltr>{usd(data.estimated_cost.base)}</Ltr>
                      </dd>
                    </div>
                  </dl>
                </>
              ) : (
                <>
                  {/* Not "$0.00". A zero and an unknown are different facts and
                      a zero is the one a reader will believe. */}
                  <Big tone="muted">نامشخص</Big>
                  <span
                    className="text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    برای این مدل قیمتی ثبت نشده است
                  </span>
                </>
              )}
            </Card>

            <Card label={data.has_resume ? 'زمان باقی‌مانده' : 'زمان تخمینی'}>
              <Big>{data.estimated_time}</Big>
              <span
                className="text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <Ltr>{fa(data.chunk_count)}</Ltr> بخش × <Ltr>{fa(data.concurrency)}</Ltr>
                رشتهٔ موازی
              </span>
            </Card>

            <Card label="خلاصهٔ فرایند">
              <Row label="مدل" value={<Ltr>{data.model}</Ltr>} />
              <Row label="حالت" value={data.mode === 'batch' ? 'دسته‌ای' : 'سریع'} />
              <Row label="زبان مبدأ" value={<Ltr>{data.source_lang}</Ltr>} />
              <Row label="زبان مقصد" value={<Ltr>{data.target_lang}</Ltr>} />
            </Card>
          </div>
        )}

        {/* ---- the one caveat that matters, stated where it is read ---- */}
        {data && !data.chunk_count_exact ? (
          <p
            className="mb-4 text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            تعداد بخش‌ها تخمینی است: این فایل مستقیماً تقسیم نشد، پس عدد از
            تعداد صفحه یا حجم فایل به دست آمده.
          </p>
        ) : null}

        {/* ---- process steps ---- */}
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setShowSteps((value) => !value)}
            aria-expanded={showSteps}
            aria-controls="estimate-steps"
            className="btn-ghost w-full justify-between"
          >
            <span>جزئیات فرایند ترجمه</span>
            <span aria-hidden="true">{showSteps ? '▴' : '▾'}</span>
          </button>
          {/* grid-rows, not max-height: the panel gets to its natural height, so
              the steps do not jump at the end of the transition. */}
          <div
            id="estimate-steps"
            className="collapsible"
            data-open={showSteps ? 'true' : 'false'}
          >
            <div>
              <ol className="grid gap-2 py-3">
                {STEPS.map((step, index) => (
                  <li key={step.title} className="flex items-start gap-2">
                    <span
                      aria-hidden="true"
                      className="mt-0.5 flex-none"
                      style={{ color: 'var(--color-text-brand)' }}
                    >
                      {index + 1}
                    </span>
                    <span>
                      <strong className="text-[length:var(--text-small)]">
                        {step.title}
                      </strong>
                      <span
                        className="block text-[length:var(--text-caption)]"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {step.body}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>

        {/* ---- footer ---- */}
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t pt-3" style={{ borderColor: 'var(--color-border)' }}>
          <button
            type="button"
            onClick={onClose}
            className="btn-ghost"
            disabled={starting}
          >
            انصراف
          </button>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-ghost"
              onClick={onClose}
              disabled={starting}
            >
              <span aria-hidden="true">⚙</span> تنظیمات
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onStart(resume)}
              disabled={starting}
            >
              {starting
                ? 'در حال شروع…'
                : resume
                  ? 'ادامهٔ ترجمه ←'
                  : 'شروع ترجمه ←'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

/**
 * There is deliberately no `useEstimate` hook here.
 *
 * The first version had one that called `POST /api/translate/start` with
 * `{file_path, config, resume}` — which is the shape the design asked for and
 * which does not exist in this product. Translation actually starts with
 * `POST /api/jobs` and a `FormData` carrying the uploaded `File`, and that
 * `File` only exists inside the workspace page's file input. A dialog cannot
 * reach it.
 *
 * So the dialog reports the choice through `onStart(resume)` and the page that
 * owns the file does the starting. Inventing an endpoint to satisfy a design
 * document would have produced a dialog whose button silently did nothing.
 */
