import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { STATUS_FA, badgeClass, fa, faBytes, faDuration } from '@/lib/format'
import { ApiStatus } from '@/components/ApiStatus'
import { KalimaMark } from '@/components/AppShell'
import { useTheme } from '@/hooks/useTheme'

/**
 * A stat tile.
 *
 * The old version tinted the whole card with `color-mix` on a tone colour and
 * coloured the number. On the new palette that produced a muddy wash, and the
 * number's colour was the only thing separating it from the label. Now the tile
 * is a plain surface and the tone is carried by a small edge marker, which
 * keeps the number itself at full text contrast.
 */
function StatCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div
      className="relative overflow-hidden rounded-[var(--radius-card)] border p-[var(--spacing-4)]"
      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
    >
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
        className="mt-[var(--spacing-1)] block ps-2 text-[length:var(--text-h1)] font-extrabold tabular-nums"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {value}
      </strong>
    </div>
  )
}

export function DashboardPage() {
  const { theme, toggle } = useTheme()

  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary, refetchInterval: 5000 })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.jobs, refetchInterval: 3000 })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: 60_000 })

  return (
    <main className="py-[var(--spacing-8)]" dir="rtl">
      <header className="mb-[var(--spacing-6)] flex flex-wrap items-start justify-between gap-[var(--spacing-4)]">
        <div className="flex items-center gap-[var(--spacing-3)]">
          <KalimaMark size={40} />
          <div>
            <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
              میز کار ترجمه
            </h1>
            <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-muted)' }}>
              KALIMA — رابط React روی همان API پایتون
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ApiStatus />
          <button
            type="button"
            onClick={toggle}
            aria-pressed={theme === 'dark'}
            aria-label="تغییر حالت روشن و تاریک"
            className="btn-icon"
          >
            <span aria-hidden="true">{theme === 'dark' ? '☀' : '◐'}</span>
          </button>
        </div>
      </header>

      <section aria-label="خلاصهٔ وضعیت" className="mb-[var(--spacing-6)] grid grid-cols-2 gap-[var(--spacing-3)] lg:grid-cols-4">
        <StatCard
          label="ترجمه‌های فعال"
          value={fa(summary.data?.active_jobs)}
          tone="var(--color-primary)"
        />
        <StatCard label="متوقف‌شده" value={fa(summary.data?.paused_jobs)} tone="var(--color-warning)" />
        <StatCard label="تکمیل‌شده" value={fa(summary.data?.completed_jobs)} tone="var(--color-success)" />
        <StatCard label="دارای خطا" value={fa(summary.data?.failed_jobs)} tone="var(--color-error)" />
      </section>

      <section className="mb-[var(--spacing-6)] grid gap-[var(--spacing-3)] sm:grid-cols-3">
        <div className="surface-card p-[var(--spacing-4)]">
          <span className="data-label">کتاب‌های کتابخانه</span>
          <strong className="data-value text-[length:var(--text-h2)]">{fa(summary.data?.total_books)}</strong>
        </div>
        <div className="surface-card p-[var(--spacing-4)]">
          <span className="data-label">فضای آزاد</span>
          <strong className="data-value text-[length:var(--text-h2)]">{faBytes(summary.data?.storage_free)}</strong>
        </div>
        <div className="surface-card p-[var(--spacing-4)]">
          <span className="data-label">مدل‌های در دسترس</span>
          <strong className="data-value text-[length:var(--text-h2)]">
            {models.isPending ? '—' : fa(models.data?.items.length)}
          </strong>
        </div>
      </section>

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="jobs-heading">
        <div className="mb-[var(--spacing-4)] flex items-center justify-between gap-[var(--spacing-3)]">
          <h2 id="jobs-heading" className="text-[length:var(--text-h2)] font-extrabold">
            کارهای اخیر
          </h2>
          <span
            className="text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {jobs.isPending ? 'در حال دریافت…' : `${fa(jobs.data?.items.length)} کار`}
          </span>
        </div>

        {jobs.isError ? (
          <p role="alert" className="alert alert-error">
            دریافت کارها ممکن نشد. مطمئن شوید سرور پایتون روی ۸۷۶۵ اجرا است.
          </p>
        ) : (
          <ul className="grid gap-2">
            {(jobs.data?.items ?? []).slice(0, 8).map((job) => (
              <li key={job.id}>
                <Link
                  to={`/jobs/${job.id}`}
                  className="flex flex-wrap items-center gap-[var(--spacing-3)] rounded-[var(--radius-control)] border p-[var(--spacing-3)] transition-colors"
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
                  <span className="min-w-0 flex-1">
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
                      {job.progress.total
                        ? `${fa(job.progress.completed)}/${fa(job.progress.total)}`
                        : '—'}
                    </span>
                  </span>
                  <span className={badgeClass(job.status)}>{STATUS_FA[job.status]}</span>
                  <span
                    className="text-[length:var(--text-caption)] tabular-nums"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {faDuration(job.eta_seconds)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
