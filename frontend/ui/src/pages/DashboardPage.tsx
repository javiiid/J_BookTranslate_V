import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Job } from '@/lib/api'
import { badgeClass, fa, faAgo, faBytes, faDuration, serverError, statusLabel } from '@/lib/format'
import { attentionQueue, bucketByDay, greeting, heroStatus, missingFromChart, todayFa, weekStats } from '@/lib/dashboard'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { ApiStatus } from '@/components/ApiStatus'
import { BarChart } from '@/components/BarChart'
import { NavIcon } from '@/components/NavIcon'
import './dashboard.css'

/**
 * The dashboard.
 *
 * ## What it is for
 *
 * Ordered by what a person opening it wants to know, in this order:
 *
 *   0. **Where am I.** A hero band with the date, a greeting and one live
 *      sentence: stuck work first, running work second, silence when there is
 *      nothing. The band also carries the primary action (add a book) and a
 *      real refresh, so the first thing on the page is a way forward.
 *   1. **The figures.** Active, paused, completed, failed -- real zeros, a
 *      skeleton while loading, and an explicit "unknown" when the summary
 *      itself failed. A tile whose number has no unit is a number nobody can
 *      act on, so every tile carries its own sentence.
 *   2. **What is stuck.** The attention queue, worst first: failed before
 *      resumable-paused, newest first within a status.
 *   3. **What is running.** Active jobs with a live progress line, so running
 *      work is visible without hunting through history.
 *   4. **How the week went.** The pulse (started, finished, cohort completion
 *      rate) plus the seven-day chart. The chart is built from the page the
 *      dashboard actually has, and it says so.
 *   5. **Everything else.** Recent jobs with a relative timestamp and a search
 *      scoped to the loaded page.
 *
 * The rail beside it holds the way forward (quick actions) and the system
 * figures (disk, models, translated sections, retries) -- numbers with no time
 * dimension, shown as a definition list rather than four more tiles.
 *
 * A first run gets none of the machinery: with zero jobs the page is the hero
 * plus three steps that teach the loop (add -> watch -> read) instead of
 * tiles of zeros.
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
 *
 * ## Polling without noise
 *
 * Jobs poll only while something can still change (a running or queued job on
 * the page); the summary polls on a fixed beat. Refetches keep the old data on
 * screen -- there is no skeleton flash and no layout jump -- and the only
 * live regions are the initial skeleton (`role="status"`, announced once) and
 * failed actions (`role="alert"`). The background-fetch note is `aria-hidden`.
 */

/** Jobs that count as running work: visible in "in progress", never in "stuck". */
const ACTIVE_STATUSES = ['running', 'queued', 'stopping'] as const

/** How many active jobs the section shows before pointing at `/jobs`. */
const ACTIVE_LIMIT = 3

/** How many recent jobs the list shows before pointing at `/jobs`. */
const RECENT_LIMIT = 5

/**
 * One overview figure.
 *
 * The tone is a small edge marker, so the number itself stays at full text
 * contrast. `value` arrives pre-resolved: a real zero, an ellipsis while its
 * query loads, or a dash when its query failed -- three states that must not
 * look like each other.
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
      <span className="dash-tile-edge" style={{ background: tone }} aria-hidden="true" />
      <span className="dash-tile-label">{label}</span>
      <strong className="dash-tile-value">{value}</strong>
      {hint ? <span className="dash-tile-hint">{hint}</span> : null}
    </>
  )
  if (to) {
    return (
      <Link to={to} className="dash-tile">
        {body}
      </Link>
    )
  }
  return <div className="dash-tile">{body}</div>
}

/**
 * One job that is still translating.
 *
 * Title, status, progress line (bar plus counts), ETA and a way into the
 * detail page. A job with no chunked total yet (queued) shows the preparing
 * line instead of a bar at zero -- a zero-width bar and "nothing happened"
 * look identical, and here zero means "not started".
 */
function ActiveJobCard({ job }: { job: Job }) {
  const { t } = useLanguage()
  const percent = Math.max(0, Math.min(100, Math.round(job.progress?.percent ?? 0)))
  const hasTotal = (job.progress?.total ?? 0) > 0
  const eta = faDuration(job.eta_seconds)
  return (
    <li className="dash-active">
      <div className="dash-active-top">
        <div className="min-w-0">
          <div className="dash-active-title-row">
            <span className={`${badgeClass(job.status)} flex-none`}>{statusLabel(job.status)}</span>
            <Link
              to={`/jobs/${job.id}`}
              dir="ltr"
              title={job.filename}
              className="dash-active-title dash-trunc"
            >
              {job.filename}
            </Link>
          </div>
          <span className="dash-active-meta">
            {job.filetype} · {job.source_language} → {job.target_language}
            {job.model ? ` · ${job.model}` : ''}
          </span>
        </div>
        <div className="dash-active-side">
          {eta === '—' ? null : <span className="dash-active-eta">{eta}</span>}
          <Link to={`/jobs/${job.id}`} className="btn btn-secondary">
            {t('dashboard.details')}
          </Link>
        </div>
      </div>
      {hasTotal ? (
        <div className="dash-active-progress">
          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label={t('dashboard.progressLabel', { name: job.filename })}
          >
            <div className="progress-fill" style={{ width: `${percent}%` }} />
          </div>
          <span className="dash-active-count">
            {fa(job.progress?.completed ?? 0)} {t('dashboard.progressOf', { total: fa(job.progress?.total ?? 0) })}
          </span>
        </div>
      ) : (
        <p className="dash-active-meta">{t('dashboard.preparing')}</p>
      )}
    </li>
  )
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
  const { t } = useLanguage()
  const resume = useMutation({
    mutationFn: () => api.resumeJob(job.id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['jobs'] })
      void client.invalidateQueries({ queryKey: ['summary'] })
    },
  })
  const done = job.progress?.percent ?? null
  // A bar needs a denominator. Without one, "0 of 0" is arithmetic homework,
  // not information -- and a zero-width bar reads as "nothing happened".
  const hasTotal = (job.progress?.total ?? 0) > 0
  const stalled = job.status === 'failed'

  return (
    <li className="dash-attention">
      <div className="dash-attention-top">
        <div className="min-w-0">
          <div className="dash-active-title-row">
            <span className={`${badgeClass(job.status)} flex-none`}>{statusLabel(job.status)}</span>
            <Link
              to={`/jobs/${job.id}`}
              dir="ltr"
              title={job.filename}
              className="dash-active-title dash-trunc"
            >
              {job.filename}
            </Link>
          </div>
          <span className="dash-active-meta">
            {job.filetype} · {job.source_language} → {job.target_language}
            {job.model ? ` · ${job.model}` : ''}
          </span>
          {done !== null && done < 100 && hasTotal ? (
            <div className="dash-active-progress">
              <div
                className="progress-track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(done)}
                aria-label={t('dashboard.progressLabel', { name: job.filename })}
              >
                <div className="progress-fill" style={{ width: `${done}%` }} />
              </div>
              <span className="dash-active-count">
                {fa(job.progress?.completed ?? 0)} {t('dashboard.progressOf', { total: fa(job.progress?.total ?? 0) })}
              </span>
            </div>
          ) : null}
          {stalled && job.error ? (
            /* The reason, in the surface's own error wash. Not the badge colour
               alone: colour is never the only signal in this project, and a
               failure row whose only cue is a red pill tells a reader who cannot
               distinguish it nothing at all. */
            <p className="alert alert-error mt-[var(--spacing-3)]">
              {serverError(job.error)}
            </p>
          ) : null}
        </div>
        <div className="dash-attention-actions">
          {job.can_resume ? (
            <button
              type="button"
              className="btn btn-primary flex-none"
              onClick={() => resume.mutate()}
              disabled={resume.isPending}
            >
              {resume.isPending ? t('dashboard.resuming') : t('dashboard.resumeNow')}
            </button>
          ) : null}
          <Link to={`/jobs/${job.id}`} className="btn btn-secondary flex-none">
            {t('dashboard.details')}
          </Link>
        </div>
      </div>
      {resume.isError ? (
        <p role="alert" className="alert alert-error mt-[var(--spacing-3)]">
          {t('dashboard.resumeFailed')}
        </p>
      ) : null}
    </li>
  )
}

export function DashboardPage() {
  const { t, lang, dir } = useLanguage()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary, refetchInterval: 15_000 })
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: api.jobs,
    // Poll only while something on the page can still change. A finished job
    // never changes, so polling a quiet account is requests for nothing.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      return items.some((job) => job.status === 'running' || job.status === 'queued') ? 2500 : false
    },
  })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: 60_000 })
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })

  const items = jobs.data?.items ?? []
  const queue = attentionQueue(items)
  const fullQueueSize = attentionQueue(items, 99).length
  const active = items.filter((job) => (ACTIVE_STATUSES as readonly string[]).includes(job.status))
  const total = jobs.data?.total ?? items.length
  const notOnPage = missingFromChart(total, items.length)
  const runningCount = active.length
  const stuckCount = fullQueueSize
  const pulse = weekStats(items)
  // A first run: no jobs anywhere, so tiles and charts would be zeros and
  // the page teaches the loop instead of reporting it.
  const isFirstRun = !jobs.isPending && !jobs.isError && items.length === 0 && total === 0

  // The last job that produced a readable file, which is what "continue
  // reading" means. A failed run has nothing to read, so it is skipped rather
  // than linked and then found to be empty.
  const lastReadable = items.find(
    (job): job is Job & { reader: string } =>
      job.status === 'completed' && typeof job.reader === 'string',
  )
  const lastUnfinished = items.find(
    (job) => job.status === 'paused' && job.can_resume === true,
  )

  const buckets = bucketByDay(items, 7, new Date(), lang)
  const needle = search.trim().toLowerCase()
  const searched = needle ? items.filter((job) => job.filename.toLowerCase().includes(needle)) : items
  const recent = searched.slice(0, RECENT_LIMIT)

  const fetching =
    summary.isFetching || jobs.isFetching || models.isFetching || analytics.isFetching
  const hasData = summary.data !== undefined || jobs.data !== undefined
  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: ['summary'] })
    void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    void queryClient.invalidateQueries({ queryKey: ['models'] })
    void queryClient.invalidateQueries({ queryKey: ['analytics'] })
  }

  // One tile value, three honest states: the number, an ellipsis while its
  // query loads, a dash when its query failed. A failed summary must not read
  // as "zero of everything".
  const tile = (pending: boolean, failed: boolean, value: number | null | undefined): string =>
    pending ? '…' : failed ? '—' : fa(value)

  return (
    <main className="page" dir={dir}>
      {/* The hero band: greeting, today's date, one live sentence, and the way
          forward. The text block carries `min-w-48` on top of `flex-1`: on a
          390px phone the status pill is ~200px of `nowrap` badge, so without a
          basis the greeting is squeezed to a word per line instead of the
          actions wrapping underneath. */}
      <header className="dash-hero">
        <div className="min-w-0" style={{ flex: '1 1 12rem' }}>
          <p className="dash-hero-eyebrow">{todayFa(new Date(), lang)}</p>
          <h1 className="dash-hero-title">
            {t('dashboard.welcome', { greeting: greeting(new Date().getHours(), lang) })}
          </h1>
          <p className="dash-hero-status">
            {jobs.isPending
              ? t('dashboard.checking')
              : jobs.isError
                // A failed fetch is not an empty account. `heroStatus` with
                // `total: 0` would point a disconnected reader at the first
                // step as if nothing existed -- a conclusion drawn from the
                // absence of data rather than from data.
                ? t('dashboard.heroError')
                : heroStatus({ running: runningCount, stuck: stuckCount, total }, lang)}
          </p>
        </div>
        <div className="dash-hero-actions">
          <Link to="/workspace" className="btn dash-hero-primary">
            {t('dashboard.addBook')}
          </Link>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={refreshAll}
            disabled={fetching}
          >
            {fetching ? t('dashboard.refreshing') : t('dashboard.refresh')}
          </button>
          <ApiStatus />
        </div>
        {fetching && hasData ? (
          <span className="dash-updating" aria-hidden="true">
            {t('dashboard.updating')}
          </span>
        ) : null}
      </header>

      {jobs.isPending ? (
        <div className="dash-skel" role="status" aria-label={t('dashboard.skeleton')}>
          <div className="dash-skel-tiles" aria-hidden="true">
            {Array.from({ length: 4 }, (_, index) => (
              <div key={index} className="skeleton" style={{ height: 108 }} />
            ))}
          </div>
          <div className="dash-layout" aria-hidden="true">
            <div className="dash-main">
              <div className="skeleton" style={{ height: 220 }} />
              <div className="skeleton" style={{ height: 160 }} />
            </div>
            <div className="dash-side">
              <div className="skeleton" style={{ height: 300 }} />
            </div>
          </div>
        </div>
      ) : isFirstRun ? (
        <FirstRunCard />
      ) : (
        <>
          {summary.isError ? (
            <div role="alert" className="alert alert-error dash-alert mb-[var(--spacing-4)]">
              <span className="dash-alert-text">{t('dashboard.summaryError')}</span>
              <button type="button" className="btn btn-secondary flex-none" onClick={() => void summary.refetch()}>
                {t('dashboard.retry')}
              </button>
            </div>
          ) : null}

          {/* The figures. Paused and failed link at `/jobs`, where the rows
              they count live; `/jobs` has no status filter, so no tile invents
              a query string for it. */}
          <div className="dash-tiles mb-[var(--spacing-4)]">
            <StatCard
              label={t('dashboard.running')}
              value={tile(summary.isPending, summary.isError, summary.data?.active_jobs)}
              tone="var(--color-primary)"
              hint={t('dashboard.runningHint')}
              to="/jobs"
            />
            <StatCard
              label={t('dashboard.paused')}
              value={tile(summary.isPending, summary.isError, summary.data?.paused_jobs)}
              tone="var(--color-warning)"
              hint={t('dashboard.pausedHint')}
              to="/jobs"
            />
            <StatCard
              label={t('dashboard.completed')}
              value={tile(summary.isPending, summary.isError, summary.data?.completed_jobs)}
              tone="var(--color-success)"
              hint={t('dashboard.completedHint', { total: fa(total) })}
            />
            <StatCard
              label={t('dashboard.failed')}
              value={tile(summary.isPending, summary.isError, summary.data?.failed_jobs)}
              tone="var(--color-error)"
              hint={t('dashboard.failedHint')}
              to="/jobs"
            />
          </div>

          <div className="dash-layout">
            <div className="dash-main">
              {jobs.isError ? (
                <div role="alert" className="alert alert-error dash-alert dash-section">
                  <span className="dash-alert-text">{t('dashboard.jobsError')}</span>
                  <button type="button" className="btn btn-secondary flex-none" onClick={() => void jobs.refetch()}>
                    {t('dashboard.retry')}
                  </button>
                </div>
              ) : (
                <>
                  {/* What is stuck first, because it is the only part of this
                      page that can change what the reader does next. */}
                  {queue.length > 0 ? (
                    <section aria-labelledby="attention-heading" className="dash-section">
                      <div className="dash-section-head">
                        <h2 id="attention-heading" className="dash-section-title">
                          {t('dashboard.attention')}
                        </h2>
                        <span className="dash-section-note">
                          {t('dashboard.jobsCount', { count: fa(queue.length) })}
                          {queue.length < fullQueueSize
                            ? ` ${t('dashboard.progressOf', { total: fa(fullQueueSize) })}`
                            : ''}
                        </span>
                      </div>
                      <ul className="dash-list">
                        {queue.map((job) => (
                          <AttentionRow key={job.id} job={job} />
                        ))}
                      </ul>
                      {queue.length < fullQueueSize ? (
                        <p className="mt-[var(--spacing-3)]">
                          <Link to="/jobs" className="btn btn-secondary">
                            {t('dashboard.viewAllJobs')}
                          </Link>
                        </p>
                      ) : null}
                    </section>
                  ) : null}

                  {/* What is running, with its progress on the card. */}
                  <section aria-labelledby="active-heading" className="dash-section">
                    <div className="dash-section-head">
                      <h2 id="active-heading" className="dash-section-title">
                        {t('dashboard.inProgress')}
                      </h2>
                      <span className="dash-section-note">
                        {t('dashboard.inProgressHint', { count: fa(active.length) })}
                      </span>
                    </div>
                    {active.length === 0 ? (
                      <p className="dash-empty">
                        {t('dashboard.noActive')} {t('dashboard.noActiveHint')}
                      </p>
                    ) : (
                      <>
                        <ul className="dash-list">
                          {active.slice(0, ACTIVE_LIMIT).map((job) => (
                            <ActiveJobCard key={job.id} job={job} />
                          ))}
                        </ul>
                        {active.length > ACTIVE_LIMIT ? (
                          <p className="mt-[var(--spacing-3)]">
                            <Link to="/jobs" className="btn btn-secondary">
                              {t('dashboard.inProgressMore', { n: fa(active.length - ACTIVE_LIMIT) })}
                            </Link>
                          </p>
                        ) : null}
                      </>
                    )}
                  </section>

                  {/* How the week went: the pulse first, then the chart. Pulse
                      figures are the week's own cohort, not a global ratio. */}
                  <section aria-label={t('dashboard.week')} className="dash-section">
                    <div className="dash-section-head">
                      <h2 className="dash-section-title">{t('dashboard.pulse')}</h2>
                      <span className="dash-section-note">{t('dashboard.pulseHint')}</span>
                    </div>
                    <div className="dash-pulse">
                      <div className="min-w-0">
                        <strong className="dash-pulse-value">{fa(pulse.started)}</strong>
                        <span className="dash-pulse-label">{t('dashboard.started')}</span>
                      </div>
                      <div className="min-w-0">
                        <strong className="dash-pulse-value">{fa(pulse.finished)}</strong>
                        <span className="dash-pulse-label">{t('dashboard.finished')}</span>
                      </div>
                      <div className="min-w-0">
                        <strong className="dash-pulse-value">
                          {pulse.rate === null ? '—' : `${fa(Math.round(pulse.rate * 100))}${lang === 'fa' ? '٪' : '%'}`}
                        </strong>
                        <span className="dash-pulse-label">{t('dashboard.rate')}</span>
                      </div>
                    </div>
                    <div className="dash-section-head">
                      <h3 className="dash-section-title" style={{ fontSize: 'var(--text-body)' }}>
                        {t('dashboard.week')}
                      </h3>
                      <span className="dash-section-note">
                        {/* Say what the chart covers. `items` is one page, and a
                            chart that silently showed 30 of 47 jobs would be a
                            chart about the wrong set. */}
                        {notOnPage > 0
                          ? t('dashboard.chartCoveragePart', { shown: fa(items.length), total: fa(total) })
                          : t('dashboard.chartCoverageAll', { shown: fa(items.length) })}
                      </span>
                    </div>
                    <BarChart
                      bars={buckets.map((bucket) => ({
                        label: bucket.label,
                        value: bucket.started,
                        title: t('dashboard.chartTitle', { started: fa(bucket.started), unfinished: fa(bucket.unfinished) }),
                      }))}
                      caption={t('dashboard.chartCaption')}
                    />
                  </section>

                  {/* Everything else: recent jobs with a search scoped to the
                      loaded page. */}
                  <section className="dash-section" aria-labelledby="jobs-heading">
                    <div className="dash-section-head">
                      <h2 id="jobs-heading" className="dash-section-title">
                        {t('dashboard.recent')}
                      </h2>
                      <Link to="/jobs" className="btn btn-secondary">
                        {t('dashboard.allJobs')}
                      </Link>
                    </div>
                    {items.length > 0 ? (
                      <div className="dash-search">
                        <input
                          type="search"
                          className="field"
                          value={search}
                          onChange={(event) => setSearch(event.target.value)}
                          placeholder={t('dashboard.searchPh')}
                          aria-label={t('dashboard.searchLabel')}
                        />
                        <span className="dash-search-scope">
                          {t('dashboard.searchScope', { shown: fa(items.length) })}
                        </span>
                      </div>
                    ) : null}
                    {recent.length === 0 ? (
                      <p className="dash-empty">
                        {needle ? t('dashboard.searchEmpty') : t('dashboard.noJobs')}
                      </p>
                    ) : (
                      <ul className="grid gap-[var(--spacing-2)]">
                        {recent.map((job) => (
                          <li key={job.id}>
                            <Link
                              to={`/jobs/${job.id}`}
                              className="grid dash-row gap-[var(--spacing-2)] rounded-[var(--radius-control)] border p-[var(--spacing-3)] no-underline transition-colors lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-[var(--spacing-3)]"
                            >
                              <span className="min-w-0">
                                <span className="flex min-w-0 items-center gap-[var(--spacing-2)]">
                                  <span className="badge flex-none">{job.filetype}</span>
                                  <strong
                                    dir="ltr"
                                    title={job.filename}
                                    className="dash-trunc block min-w-0 flex-1 truncate text-[length:var(--text-body)]"
                                    style={{ color: 'var(--color-text-primary)' }}
                                  >
                                    {job.filename}
                                  </strong>
                                </span>
                                <span
                                  className="mt-[var(--spacing-1)] block break-words text-[length:var(--text-caption)]"
                                  style={{ color: 'var(--color-text-muted)' }}
                                >
                                  {job.filetype} · {job.source_language} → {job.target_language} ·{' '}
                                  {job.progress?.total
                                    ? `${fa(job.progress.completed)}/${fa(job.progress.total)}`
                                    : '—'}{' '}
                                  · {faAgo(job.updated_at)}
                                </span>
                              </span>
                              {/* The badge sits above the ETA, stacked, in one wrapper.
                                  They were siblings of a wrapping row, so on a phone the
                                  title took line one and these two dropped to line two at the
                                  far edge, leaving a gap the width of the title beside them. */}
                              <span className="flex flex-col items-center gap-[var(--spacing-1)]">
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
            </div>

            <div className="dash-side">
              {/* What to do next. */}
              <section aria-label={t('dashboard.quickAccess')} className="dash-section">
                <div className="dash-section-head">
                  <h2 className="dash-section-title" style={{ fontSize: 'var(--text-body)' }}>
                    {t('dashboard.quickAccess')}
                  </h2>
                </div>
                <ul className="dash-quick">
                  <li>
                    <Link
                      to={lastUnfinished ? `/jobs/${lastUnfinished.id}` : '/workspace'}
                      className="dash-quick-card"
                    >
                      <span className="dash-quick-icon" aria-hidden="true">
                        <NavIcon name="add" size={20} />
                      </span>
                      <span className="min-w-0">
                        <strong className="dash-quick-title">
                          {lastUnfinished ? t('dashboard.resumeJob') : t('dashboard.addBook')}
                        </strong>
                        <small
                          dir="ltr"
                          title={lastUnfinished ? lastUnfinished.filename : undefined}
                          className="dash-quick-sub dash-trunc"
                        >
                          {lastUnfinished ? lastUnfinished.filename : t('dashboard.addBookHint')}
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
                      <a href={lastReadable.reader} className="dash-quick-card">
                        <span className="dash-quick-icon" aria-hidden="true">
                          <NavIcon name="reader" size={20} />
                        </span>
                        <span className="min-w-0">
                          <strong className="dash-quick-title">{t('dashboard.read')}</strong>
                          <small dir="ltr" title={lastReadable.filename} className="dash-quick-sub dash-trunc">
                            {lastReadable.filename}
                          </small>
                        </span>
                      </a>
                    ) : (
                      <Link to="/library" className="dash-quick-card">
                        <span className="dash-quick-icon" aria-hidden="true">
                          <NavIcon name="reader" size={20} />
                        </span>
                        <span className="min-w-0">
                          <strong className="dash-quick-title">{t('dashboard.read')}</strong>
                          <small className="dash-quick-sub">{t('dashboard.readEmpty')}</small>
                        </span>
                      </Link>
                    )}
                  </li>
                  <li>
                    <Link to="/convert" className="dash-quick-card">
                      <span className="dash-quick-icon" aria-hidden="true">
                        <NavIcon name="convert" size={20} />
                      </span>
                      <span className="min-w-0">
                        <strong className="dash-quick-title">{t('dashboard.convert')}</strong>
                        <small className="dash-quick-sub">{t('dashboard.convertHint')}</small>
                      </span>
                    </Link>
                  </li>
                  <li>
                    <Link to="/library" className="dash-quick-card">
                      <span className="dash-quick-icon" aria-hidden="true">
                        <NavIcon name="library" size={20} />
                      </span>
                      <span className="min-w-0">
                        <strong className="dash-quick-title">{t('dashboard.library')}</strong>
                        <small className="dash-quick-sub">
                          {t('dashboard.libraryHint', {
                            count: summary.isPending ? '…' : summary.isError ? '—' : fa(summary.data?.total_books ?? 0),
                          })}
                        </small>
                      </span>
                    </Link>
                  </li>
                  {/* The help center, in quick access rather than the mobile bar:
                      the bar stays five destinations (the 12px floor), so this
                      card is how a phone reaches `/help` in one tap. */}
                  <li>
                    <Link to="/help" className="dash-quick-card">
                      <span className="dash-quick-icon" aria-hidden="true">
                        <NavIcon name="help" size={20} />
                      </span>
                      <span className="min-w-0">
                        <strong className="dash-quick-title">{t('nav.help')}</strong>
                        <small className="dash-quick-sub">{t('help.dashHint')}</small>
                      </span>
                    </Link>
                  </li>
                </ul>
              </section>

              {/* The system figures: disk, models, translated sections, retries.
                  No time dimension, so a definition list rather than tiles. */}
              <section aria-labelledby="system-heading" className="dash-section">
                <div className="dash-section-head">
                  <h2 id="system-heading" className="dash-section-title" style={{ fontSize: 'var(--text-body)' }}>
                    {t('dashboard.system')}
                  </h2>
                  {analytics.isError || models.isError ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ minHeight: 32, paddingInline: 'var(--spacing-3)' }}
                      onClick={() => {
                        void analytics.refetch()
                        void models.refetch()
                      }}
                    >
                      {t('dashboard.retry')}
                    </button>
                  ) : null}
                </div>
                {analytics.isError && models.isError ? (
                  <p role="alert" className="alert alert-error">
                    {t('dashboard.systemError')}
                  </p>
                ) : (
                  <dl className="dash-sys">
                    <div className="dash-sys-row">
                      <dt className="dash-sys-label">{t('dashboard.diskFree')}</dt>
                      <dd className="dash-sys-value">
                        {summary.isPending ? '…' : summary.isError ? t('dashboard.unavailable') : faBytes(summary.data?.storage_free)}
                      </dd>
                    </div>
                    <div className="dash-sys-row">
                      <dt className="dash-sys-label">{t('dashboard.models')}</dt>
                      <dd className="dash-sys-value">
                        {models.isPending ? '…' : models.isError ? t('dashboard.unavailable') : fa(models.data?.items.length)}
                      </dd>
                    </div>
                    <div className="dash-sys-row">
                      <dt className="dash-sys-label">{t('dashboard.chunks')}</dt>
                      <dd className="dash-sys-value">
                        {analytics.isPending ? '…' : analytics.isError ? t('dashboard.unavailable') : fa(analytics.data?.completed_chunks)}
                      </dd>
                    </div>
                    <div className="dash-sys-row">
                      <dt className="dash-sys-label">{t('dashboard.retries')}</dt>
                      <dd className="dash-sys-value">
                        {analytics.isPending ? '…' : analytics.isError ? t('dashboard.unavailable') : fa(analytics.data?.retries)}
                      </dd>
                    </div>
                  </dl>
                )}
              </section>
            </div>
          </div>
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
  const { t } = useLanguage()
  const steps = [
    {
      to: '/workspace',
      title: t('dashboard.step1Title'),
      body: t('dashboard.step1Body'),
    },
    {
      to: '/jobs',
      title: t('dashboard.step2Title'),
      body: t('dashboard.step2Body'),
    },
    {
      to: '/library',
      title: t('dashboard.step3Title'),
      body: t('dashboard.step3Body'),
    },
  ]
  return (
    <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="firstrun-heading">
      <h2 id="firstrun-heading" className="text-[length:var(--text-h2)] font-extrabold">
        {t('dashboard.firstRunTitle')}
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
