import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Job } from '@/lib/api'
import { badgeClass, fa, faAgo, faBytes, faDuration, statusLabel } from '@/lib/format'
import { attentionQueue, bucketByDay, greeting, heroStatus, missingFromChart, todayFa, weekStats } from '@/lib/dashboard'
import { ApiStatus } from '@/components/ApiStatus'
import { KalimaMark } from '@/components/AppShell'
import { BarChart } from '@/components/BarChart'
import { NavIcon } from '@/components/NavIcon'

/**
 * A stat tile.
 *
 * The old version tinted the whole card with `color-mix` on a tone colour and
 * coloured the number. On the new palette that produced a muddy wash, and the
 * number's colour was the only thing separating it from the label. Now the tile
 * is a plain surface and the tone is carried by a small edge marker, which
 * keeps the number itself at full text contrast.
 *
 * `hint` is optional and is the tile's own explanation. It is a real sentence
 * rather than a fragment, because a tile whose number has no unit is a number
 * nobody can act on -- "457" is a fact, "457 بخش ترجمه‌شده" is information.
 */
function StatCard({
  label,
  value,
  tone,
  hint,
  to,
}: {
  label: string
  value: string
  tone: string
  hint?: string
  to?: string
}) {
  const body = (
    <>
      <span
        className="absolute inset-block-0 start-0 w-[3px]"
        style={{ background: tone }}
        aria-hidden="true"
      />
      <span
        className="block ps-2 text-[length:var(--text-caption)] font-semibold"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </span>
      <strong
        className="mt-[var(--spacing-1)] block ps-2 text-[length:var(--text-h2)] font-extrabold tabular-nums"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {value}
      </strong>
      {hint ? (
        <span
          className="mt-[var(--spacing-1)] block ps-2 text-[length:var(--text-caption)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {hint}
        </span>
      ) : null}
    </>
  )
  const className =
    'surface-card relative block overflow-hidden p-[var(--spacing-4)] no-underline'
  if (to) {
    return (
      <Link to={to} className={className}>
        {body}
      </Link>
    )
  }
  return <div className={className}>{body}</div>
}

/**
 * One job that is waiting on a decision.
 *
 * The two actions are the safe ones, and the difference between them is the
 * point: "ادامه" spends money -- it resumes a translation and calls the model
 * again -- so it is a button that says so and it is only on a job the backend
 * has marked `can_resume`. "خواندن" spends nothing, so it is a link.
 *
 * A failed job gets neither, because `can_resume` is false on every failed job
 * in the database. It gets the error instead, because the useful thing to do
 * with a failure is read why it failed.
 */
function AttentionRow({ job }: { job: Job }) {
  const client = useQueryClient()
  const resume = useMutation({
    mutationFn: () => api.resumeJob(job.id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['jobs'] })
      void client.invalidateQueries({ queryKey: ['summary'] })
    },
  })
  // `progress.percent` is a required number on Job, so there is nothing to
  // defend against here; an earlier version computed it from completed/total
  // and had to guess what an absent progress meant.
  const done = job.progress?.percent ?? null
  const stalled = job.status === 'failed'

  return (
    <li className="surface-card p-[var(--spacing-4)]">
      <div className="grid gap-[var(--spacing-3)] lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-[var(--spacing-2)]">
            <span className={badgeClass(job.status)}>{statusLabel(job.status)}</span>
            <Link
              to={`/jobs/${job.id}`}
              className="min-w-0 truncate text-[length:var(--text-body)] font-semibold no-underline"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {job.filename}
            </Link>
          </div>
          <span
            className="mt-[var(--spacing-1)] block text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {job.filetype} · {job.source_language} → {job.target_language}
            {job.model ? ` · ${job.model}` : ''}
          </span>
          {done !== null && done < 100 ? (
            <div className="mt-[var(--spacing-2)] flex items-center gap-[var(--spacing-2)]">
              <div
                className="progress-track flex-1"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(done)}
                aria-label={`پیشرفت ترجمهٔ ${job.filename}`}
              >
                <div className="progress-fill" style={{ width: `${done}%` }} />
              </div>
              <span
                className="text-[length:var(--text-caption)] tabular-nums"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {fa(job.progress?.completed ?? 0)} از {fa(job.progress?.total ?? 0)}
              </span>
            </div>
          ) : null}
          {stalled && job.error ? (
            /* The reason, in the surface's own error wash. Not the badge colour
               alone: colour is never the only signal in this project, and a
               failure row whose only cue is a red pill tells a reader who cannot
               distinguish it nothing at all. */
            <p className="alert alert-error mt-[var(--spacing-3)]">
              {job.error}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-[var(--spacing-2)]">
          {job.can_resume ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => resume.mutate()}
              disabled={resume.isPending}
            >
              {resume.isPending ? 'در حال ادامه…' : 'ادامه'}
            </button>
          ) : null}
          <Link to={`/jobs/${job.id}`} className="btn btn-secondary">
            جزئیات
          </Link>
        </div>
      </div>
      {resume.isError ? (
        <p role="alert" className="alert alert-error mt-[var(--spacing-3)]">
          ادامه دادن ممکن نشد. ممکن است کلید ارائه‌دهنده در دسترس نباشد.
        </p>
      ) : null}
    </li>
  )
}

/**
 * The dashboard.
 *
 * ## What it is for
 *
 * It used to show four numbers and eight recent jobs, and offer nothing to do
 * with either. The numbers came from `dashboard/summary` and the list from
 * `/api/jobs`; everything else the API returns went unused -- including
 * `analytics/overview`, which nobody called.
 *
 * It is now ordered by what a person opening it wants to know, in this order:
 *
 *   0. **Where am I.** A greeting with today's date and one live sentence:
 *      stuck work first, running work second, silence when there is nothing.
 *   1. **What is stuck.** The attention queue, worst first. On the data this
 *      was written against that is 13 failed and 1 paused out of 30 jobs --
 *      nearly half the account, none of it visible anywhere in the interface.
 *   2. **What to do next.** Four shortcuts to the things people actually do:
 *      continue the last book, read it, open the library, convert a file.
 *   3. **How it is going.** The week's pulse (started, finished, cohort
 *      completion rate), the totals that have no time dimension, and the chart.
 *   4. **Everything else.** Recent jobs with a relative timestamp, for the
 *      ones that need no decision. Five, not eight: the full list lives on
 *      `/jobs` behind the link beside the heading, and a second full job
 *      list is how a dashboard turns into an endless scroll ending in
 *      whitespace.
 *
 * A first run gets none of the machinery: with zero jobs the page is a
 * greeting, the shortcuts, and three steps that teach the loop
 * (add -> watch -> read) instead of four tiles of zeros.
 *
 * ## What it will not do
 *
 * There is no delete, no force-restart, and no retry-without-confirmation on
 * this page. Resuming a translation spends money -- it calls the model again --
 * so the button says what it costs by being a real button on a real job, and
 * there is nothing here that can destroy work.
 *
 * There is also no cost tile. `dashboard/summary` answers `estimated_cost`
 * with a hardcoded `0.0`, and `$0.00` beside a "start translating" button
 * reads as "free" rather than "unknown" -- so the number stays off the page
 * until the backend measures it.
 */
export function DashboardPage() {
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary, refetchInterval: 5000 })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.jobs, refetchInterval: 3000 })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: 60_000 })
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })

  const items = jobs.data?.items ?? []
  const queue = attentionQueue(items)
  const total = jobs.data?.total ?? items.length
  const notOnPage = missingFromChart(total, items.length)
  // The full stuck count, not the 4 shown: the hero sentence must not claim
  // "1 needs attention" when 13 do.
  const stuckCount = attentionQueue(items, 99).length
  const runningCount = items.filter((job) => job.status === 'running').length
  const pulse = weekStats(items)
  // A first run: no jobs anywhere, so tiles and charts would be zeros and
  // the page teaches the loop instead of reporting it.
  const isFirstRun = !jobs.isPending && !jobs.isError && items.length === 0 && total === 0

  // The last job that produced a readable file, which is what "continue
  // reading" means. A failed run has nothing to read, so it is skipped rather
  // than linked and then found to be empty.
  // A completed job with a reader path is the only thing that can be opened,
  // and the path is optional on the type, so the narrowing happens here and
  // the two uses below read a plain `string | undefined`.
  const lastReadable = items.find(
    (job): job is Job & { reader: string } =>
      job.status === 'completed' && typeof job.reader === 'string',
  )
  const lastUnfinished = items.find(
    (job) => job.status === 'paused' && job.can_resume === true,
  )

  const buckets = bucketByDay(items)

  return (
    <main className="page" dir="rtl">
      {/* 0. Where am I. A greeting, today's date, and one live sentence.
          The text block carries `min-w-48` on top of `flex-1`: on a 390px
          phone the status pill is ~200px of `nowrap` badge, so without a
          basis the greeting is squeezed to a word per line instead of the
          pill wrapping underneath. */}
      <header className="surface-card mb-[var(--spacing-6)] flex flex-wrap items-center gap-[var(--spacing-4)] p-[var(--spacing-5)]">
        <KalimaMark size={48} />
        <div className="min-w-0" style={{ flex: '1 1 12rem' }}>
          <p
            className="text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {todayFa()}
          </p>
          <h1 className="mt-[var(--spacing-1)] text-[length:var(--text-h1)] font-extrabold tracking-tight">
            {greeting(new Date().getHours())}؛ به کالیما خوش آمدید
          </h1>
          <p
            className="mt-[var(--spacing-1)] text-[length:var(--text-small)]"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {jobs.isPending
              ? 'در حال سر زدن به کارها…'
              : heroStatus({ running: runningCount, stuck: stuckCount, total })}
          </p>
        </div>
        <ApiStatus />
      </header>

      {isFirstRun ? (
        <FirstRunCard />
      ) : (
        <>
      {/* 1. What is stuck. First, because it is the only part of this page that
          can change what the reader does next. */}
      {queue.length > 0 ? (
        <section aria-labelledby="attention-heading" className="mb-[var(--spacing-6)]">
          <div className="mb-[var(--spacing-3)] flex flex-wrap items-baseline justify-between gap-[var(--spacing-3)]">
            <h2 id="attention-heading" className="text-[length:var(--text-h3)] font-extrabold">
              نیازمند توجه
            </h2>
            <span
              className="text-[length:var(--text-caption)] tabular-nums"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {fa(queue.length)} کار
              {queue.length < attentionQueue(items, 99).length
                ? ` از ${fa(attentionQueue(items, 99).length)}`
                : ''}
            </span>
          </div>
          <ul className="grid gap-[var(--spacing-3)]">
            {queue.map((job) => (
              <AttentionRow key={job.id} job={job} />
            ))}
          </ul>
          {queue.length === attentionQueue(items, 99).length ? null : (
            <p className="mt-[var(--spacing-3)]">
              <Link to="/jobs" className="btn btn-secondary">
                دیدن همهٔ کارها
              </Link>
            </p>
          )}
        </section>
      ) : null}

      {/* 2. What to do next. */}
      <section aria-label="دسترسی سریع" className="mb-[var(--spacing-6)]">
        <ul className="grid gap-[var(--spacing-3)] sm:grid-cols-2 lg:grid-cols-4">
          <li>
            <Link
              to={lastUnfinished ? `/jobs/${lastUnfinished.id}` : '/workspace'}
              className="surface-card flex h-full items-center gap-[var(--spacing-3)] p-[var(--spacing-4)] no-underline"
            >
              <span
                className="grid size-10 flex-none place-items-center rounded-full"
                style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
              >
                <NavIcon name="add" size={20} />
              </span>
              <span className="min-w-0">
                <strong className="block text-[length:var(--text-body)]">
                  {lastUnfinished ? 'ادامهٔ ترجمه' : 'افزودن کتاب'}
                </strong>
                <small
                  className="block truncate text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {lastUnfinished ? lastUnfinished.filename : 'یک EPUB یا PDF تازه'}
                </small>
              </span>
            </Link>
          </li>
          {/* `job.reader` is a BACKEND path (`/reader/<id>`), not a React route:
              a `<Link to>` would be intercepted by the router and land on the
              `ReaderHandedOver` placeholder. A plain anchor leaves the SPA for
              the Python reader, which is the point of the card. */}
          <li>
            {lastReadable ? (
              <a
                href={lastReadable.reader}
                className="surface-card flex h-full items-center gap-[var(--spacing-3)] p-[var(--spacing-4)] no-underline"
              >
                <span
                  className="grid size-10 flex-none place-items-center rounded-full"
                  style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
                >
                  <NavIcon name="reader" size={20} />
                </span>
                <span className="min-w-0">
                  <strong className="block text-[length:var(--text-body)]">مطالعه</strong>
                  <small
                    className="block truncate text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {lastReadable.filename}
                  </small>
                </span>
              </a>
            ) : (
              <Link
                to="/library"
                className="surface-card flex h-full items-center gap-[var(--spacing-3)] p-[var(--spacing-4)] no-underline"
              >
                <span
                  className="grid size-10 flex-none place-items-center rounded-full"
                  style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
                >
                  <NavIcon name="reader" size={20} />
                </span>
                <span className="min-w-0">
                  <strong className="block text-[length:var(--text-body)]">مطالعه</strong>
                  <small
                    className="block truncate text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    هنوز کتابی آماده نیست
                  </small>
                </span>
              </Link>
            )}
          </li>
          <li>
            <Link
              to="/convert"
              className="surface-card flex h-full items-center gap-[var(--spacing-3)] p-[var(--spacing-4)] no-underline"
            >
              <span
                className="grid size-10 flex-none place-items-center rounded-full"
                style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
              >
                <NavIcon name="convert" size={20} />
              </span>
              <span className="min-w-0">
                <strong className="block text-[length:var(--text-body)]">تبدیل فایل</strong>
                <small
                  className="block truncate text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Word و PDF، بدون ترجمه
                </small>
              </span>
            </Link>
          </li>
          <li>
            <Link
              to="/library"
              className="surface-card flex h-full items-center gap-[var(--spacing-3)] p-[var(--spacing-4)] no-underline"
            >
              <span
                className="grid size-10 flex-none place-items-center rounded-full"
                style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
              >
                <NavIcon name="library" size={20} />
              </span>
              <span className="min-w-0">
                <strong className="block text-[length:var(--text-body)]">کتابخانه</strong>
                <small
                  className="block truncate text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {fa(summary.data?.total_books ?? 0)} کتاب
                </small>
              </span>
            </Link>
          </li>
        </ul>
      </section>

      {/* 3. How it is going. The pulse first: what started this week and how
          much of it finished. Then the tiles, which are the totals that have
          no time dimension and so belong in tiles rather than a chart. */}
      <section aria-label="وضعیت" className="mb-[var(--spacing-6)]">
        <div className="surface-card mb-[var(--spacing-3)] p-[var(--spacing-4)]">
          <div className="mb-[var(--spacing-3)] flex flex-wrap items-baseline justify-between gap-[var(--spacing-3)]">
            <h2 className="text-[length:var(--text-body)] font-extrabold">نبض هفته</h2>
            <span
              className="text-[length:var(--text-caption)]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              از کتاب‌هایی که این هفته شروع شدند
            </span>
          </div>
          <div className="grid grid-cols-3 gap-[var(--spacing-3)]">
            <div className="min-w-0">
              <strong
                className="block text-[length:var(--text-h1)] font-extrabold tabular-nums"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {fa(pulse.started)}
              </strong>
              <span
                className="mt-[var(--spacing-1)] block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                کتاب شروع‌شده
              </span>
            </div>
            <div className="min-w-0">
              <strong
                className="block text-[length:var(--text-h1)] font-extrabold tabular-nums"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {fa(pulse.finished)}
              </strong>
              <span
                className="mt-[var(--spacing-1)] block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                به سرانجام رسیده
              </span>
            </div>
            <div className="min-w-0">
              <strong
                className="block text-[length:var(--text-h1)] font-extrabold tabular-nums"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {pulse.rate === null ? '—' : `${fa(Math.round(pulse.rate * 100))}٪`}
              </strong>
              <span
                className="mt-[var(--spacing-1)] block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                نرخ اتمام هفته
              </span>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-[var(--spacing-3)] lg:grid-cols-4">
          <StatCard
            label="در حال ترجمه"
            value={fa(summary.data?.active_jobs)}
            tone="var(--color-primary)"
            hint="همین حالا در حال اجرا"
          />
          <StatCard
            label="متوقف"
            value={fa(summary.data?.paused_jobs)}
            tone="var(--color-warning)"
            hint="منتظر ادامه"
            to="/jobs"
          />
          <StatCard
            label="تکمیل‌شده"
            value={fa(summary.data?.completed_jobs)}
            tone="var(--color-success)"
            hint={`از ${fa(total)} کار`}
          />
          <StatCard
            label="ناموفق"
            value={fa(summary.data?.failed_jobs)}
            tone="var(--color-error)"
            hint="نیازمند بررسی"
            to="/jobs"
          />
        </div>

        <div className="surface-card mt-[var(--spacing-3)] p-[var(--spacing-4)]">
          <div className="mb-[var(--spacing-3)] flex flex-wrap items-baseline justify-between gap-[var(--spacing-3)]">
            <h2 className="text-[length:var(--text-body)] font-extrabold">هفت روز گذشته</h2>
            <span
              className="text-[length:var(--text-caption)] tabular-nums"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {/* Say what the chart covers. `items` is one page, and a chart
                  that silently showed 30 of 47 jobs would be a chart about the
                  wrong set. */}
              {notOnPage > 0
                ? `${fa(items.length)} کار از ${fa(total)}`
                : `${fa(items.length)} کار`}
            </span>
          </div>
          <BarChart
            bars={buckets.map((bucket) => ({
              label: bucket.label,
              value: bucket.started,
              title: `${bucket.started} کار تازه، ${bucket.unfinished} ناتمام`,
            }))}
            caption="کارهای تازه در هفت روز گذشته، بر پایهٔ روز شروع"
          />
        </div>

        <div className="mt-[var(--spacing-3)] grid grid-cols-2 gap-[var(--spacing-3)] lg:grid-cols-4">
          <StatCard
            label="بخش ترجمه‌شده"
            value={fa(analytics.data?.completed_chunks)}
            tone="var(--color-primary)"
            hint="در مجموع"
          />
          <StatCard
            label="تلاش مجدد"
            value={fa(analytics.data?.retries)}
            tone="var(--color-warning)"
            hint="خطاهای بازگشتی"
          />
          <StatCard
            label="مدل‌های در دسترس"
            value={fa(models.data?.items.length)}
            tone="var(--color-primary)"
            hint="برای ترجمه"
          />
          <StatCard
            label="فضای آزاد"
            value={faBytes(summary.data?.storage_free)}
            tone="var(--color-success)"
            hint="روی دیسک"
          />
        </div>
      </section>

      {/* 4. Everything else. */}
      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="jobs-heading">
        <div className="mb-[var(--spacing-4)] flex flex-wrap items-center justify-between gap-[var(--spacing-3)]">
          <h2 id="jobs-heading" className="text-[length:var(--text-h2)] font-extrabold">
            کارهای اخیر
          </h2>
          <Link to="/jobs" className="btn btn-secondary">
            همهٔ کارها
          </Link>
        </div>

        {jobs.isError ? (
          <p role="alert" className="alert alert-error">
            دریافت کارها ممکن نشد. مطمئن شوید سرور پایتون روی ۸۷۶۵ اجرا است.
          </p>
        ) : items.length === 0 ? (
          <p className="empty">هنوز کاری ثبت نشده است.</p>
        ) : (
          <ul className="grid gap-[var(--spacing-2)]">
            {items.slice(0, 5).map((job) => (
              <li key={job.id}>
                <Link
                  to={`/jobs/${job.id}`}
                  className="grid gap-[var(--spacing-2)] rounded-[var(--radius-control)] border p-[var(--spacing-3)] no-underline transition-colors lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center lg:gap-[var(--spacing-3)]"
                  style={{ borderColor: 'var(--color-border)' }}
                  onMouseEnter={(event) => {
                    event.currentTarget.style.borderColor = 'var(--color-primary)'
                    event.currentTarget.style.background = 'var(--color-surface-elevated)'
                  }}
                  onMouseLeave={(event) => {
                    event.currentTarget.style.borderColor = 'var(--color-border)'
                    event.currentTarget.style.background = 'transparent'
                  }}
                >
                  <span className="min-w-0">
                    <strong
                      className="block truncate text-[length:var(--text-body)]"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {job.filename}
                    </strong>
                    <span
                      className="block text-[length:var(--text-caption)]"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {job.filetype} · {job.source_language} → {job.target_language} ·{' '}
                      {job.progress?.total
                        ? `${fa(job.progress.completed)}/${fa(job.progress.total)}`
                        : '—'}{' '}
                      · {faAgo(job.updated_at)}
                    </span>
                  </span>
                  {/* The status and the ETA travel together, tight, on one line.
                      They were siblings of a wrapping row, so on a phone the
                      title took line one and these two dropped to line two at the
                      far edge, leaving a gap the width of the title beside them. */}
                  <span className="flex items-center gap-[var(--spacing-2)]">
                    <span className={badgeClass(job.status)}>{statusLabel(job.status)}</span>
                    <span
                      className="text-[length:var(--text-caption)] tabular-nums"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {faDuration(job.eta_seconds)}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
        </>
      )}
    </main>
  )
}

/**
 * The first run: three steps that teach the loop (add -> watch -> read).
 *
 * Shown instead of the machinery when there are zero jobs, because four
 * tiles of zeros and an empty chart teach nothing. Each step links where it
 * happens, so the card is a path, not a poster.
 */
function FirstRunCard() {
  const steps = [
    {
      to: '/workspace',
      title: 'کتاب را اضافه کنید',
      body: 'یک EPUB یا PDF بدهید؛ هزینه و زمان را پیش از شروع می‌بینید و چیزی خرج نمی‌شود.',
    },
    {
      to: '/jobs',
      title: 'پیشرفت را ببینید',
      body: 'هر بخش که آماده شد همان‌جا می‌ماند؛ توقف یعنی ادامه از همان‌جا، نه از صفر.',
    },
    {
      to: '/library',
      title: 'کنار متن اصلی بخوانید',
      body: 'نسخهٔ دوزبانه از کتابخانه باز می‌شود؛ واژه‌نامه را پیش‌تر خودتان تأیید کرده‌اید.',
    },
  ]
  return (
    <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="firstrun-heading">
      <h2 id="firstrun-heading" className="text-[length:var(--text-h2)] font-extrabold">
        سه قدم تا اولین ترجمه
      </h2>
      <ol className="mt-[var(--spacing-4)] grid gap-[var(--spacing-3)]">
        {steps.map((step, index) => (
          <li key={step.to + step.title}>
            <Link
              to={step.to}
              className="flex items-start gap-[var(--spacing-3)] rounded-[var(--radius-control)] border p-[var(--spacing-3)] no-underline transition-colors"
              style={{ borderColor: 'var(--color-border)' }}
              onMouseEnter={(event) => {
                event.currentTarget.style.borderColor = 'var(--color-primary)'
                event.currentTarget.style.background = 'var(--color-surface-elevated)'
              }}
              onMouseLeave={(event) => {
                event.currentTarget.style.borderColor = 'var(--color-border)'
                event.currentTarget.style.background = 'transparent'
              }}
            >
              <span
                className="grid size-8 flex-none place-items-center rounded-full text-[length:var(--text-small)] font-extrabold tabular-nums"
                style={{ background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }}
                aria-hidden="true"
              >
                {fa(index + 1)}
              </span>
              <span className="min-w-0">
                <strong
                  className="block text-[length:var(--text-body)]"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  {step.title}
                </strong>
                <span
                  className="mt-[var(--spacing-1)] block text-[length:var(--text-small)]"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {step.body}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}
