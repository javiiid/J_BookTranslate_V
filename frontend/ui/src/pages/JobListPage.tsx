import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { badgeClass, fa, faDate, faDuration, serverError, statusLabel } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'

/**
 * The job list.
 *
 * Extracted from the dashboard, which was mixing "recent jobs" into the
 * overview page. Polls only while something is actually running: a finished
 * job never changes, so there is nothing to poll for.
 */
export function JobListPage() {
  const { t, dir, lang } = useLanguage()
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: api.jobs,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      return items.some((job) => job.status === 'running' || job.status === 'queued')
        ? 2500
        : false
    },
  })

  const items = jobs.data?.items ?? []
  const running = items.filter((job) => job.status === 'running').length

  return (
    <main className="page" dir={dir}>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
            {t('monitor.title')}
          </h1>
          <p
            className="mt-1 text-[length:var(--text-small)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {jobs.isPending
              ? t('jobs.loading')
              : `${t('jobs.count', { n: fa(items.length) })}${running ? ` · ${t('jobs.runningNow', { r: fa(running) })}` : ''}`}
          </p>
        </div>
        <Link to="/workspace" className="btn btn-primary">
          {t('dashboard.addBook')}
        </Link>
      </header>

      {jobs.isError ? (
        <p role="alert" className="alert alert-error">
          {t('dashboard.jobsError')}
        </p>
      ) : jobs.isPending ? (
        <ul className="grid gap-2">
          {Array.from({ length: 5 }, (_, index) => (
            <li key={index}>
              <div className="skeleton" style={{ height: 68 }} />
            </li>
          ))}
        </ul>
      ) : items.length === 0 ? (
        <p className="empty">{t('dashboard.noJobs')}</p>
      ) : (
        <ul className="grid gap-2">
          {items.map((job) => {
            const percent = job.progress.total
              ? Math.round((job.progress.completed / job.progress.total) * 100)
              : 0
            return (
              <li key={job.id}>
                <Link
                  to={`/jobs/${job.id}`}
                  className="surface-card block p-4 transition-colors"
                  onMouseEnter={(event) => {
                    event.currentTarget.style.borderColor = 'var(--color-primary)'
                  }}
                  onMouseLeave={(event) => {
                    event.currentTarget.style.borderColor = 'var(--color-border)'
                  }}
                >
                  {/* Stacked below `lg`, one line above it.

                      As a `flex-wrap` row the title took the full width and the
                      badge and the counter dropped to the second line at the far
                      edge, leaving a gap the width of the title beside them --
                      the same "too little here, too much there" the dashboard
                      had. A grid gives each its own row on a phone and puts
                      them back on one line on a desktop. */}
                  <div className="grid gap-[var(--spacing-2)] lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-3">
                    <div className="min-w-0">
                      <span className="flex min-w-0 items-center gap-[var(--spacing-2)]">
                        <span className="badge flex-none">{job.filetype}</span>
                        <strong className="block min-w-0 flex-1 truncate text-[length:var(--text-body)]">
                          {job.filename}
                        </strong>
                      </span>
                      <span
                        className="mt-[var(--spacing-1)] block break-words text-[length:var(--text-caption)]"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {job.source_language} → {job.target_language} · {job.model} ·{' '}
                        {faDate(job.created_at)}
                      </span>
                    </div>
                    {/* The badge sits above the counter, stacked, in one wrapper:
                        badge first, count beneath it. They travel as one unit
                        so they can never separate onto opposite ends of a row. */}
                    <span className="flex flex-col items-center gap-[var(--spacing-1)]">
                      <span className={badgeClass(job.status)}>{statusLabel(job.status)}</span>
                      <span
                        className="text-[length:var(--text-label)] tabular-nums"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {job.progress.total
                          ? `${fa(job.progress.completed)}/${fa(job.progress.total)}`
                          : faDuration(job.eta_seconds)}
                      </span>
                    </span>
                  </div>

                  {job.progress.total > 0 ? (
                    /* The bar and its percentage are one unit: a 12px gap
                       between them on a 361px line is a third of the content
                       width spent on air. The gap drops to the smallest token
                       below `lg`. */
                    <div className="mt-3 flex items-center gap-[var(--spacing-2)] lg:gap-3">
                      <div
                        className="progress-track min-w-0 flex-1"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={percent}
                        aria-label={t('jobs.progressAria', { name: job.filename })}
                      >
                        <div className="progress-fill" style={{ width: `${percent}%` }} />
                      </div>
                      <span
                        className="flex-none text-[length:var(--text-caption)] tabular-nums"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {fa(percent)}{lang === 'en' ? '%' : '٪'}
                      </span>
                    </div>
                  ) : null}

                  {job.error ? (
                    <p
                      className="mt-2 text-[length:var(--text-caption)]"
                      style={{ color: 'var(--color-error)' }}
                    >
                      {serverError(job.error)}
                    </p>
                  ) : null}
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </main>
  )
}

// Re-exported so the tone map stays discoverable from one place.
