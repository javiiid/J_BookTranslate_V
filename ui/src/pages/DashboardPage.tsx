import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { BADGE_CLASS, STATUS_FA, fa, faBytes, faDuration } from '@/lib/format'
import { ApiStatus } from '@/components/ApiStatus'
import { useTheme } from '@/hooks/useTheme'

function StatCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div
      className="rounded-2xl border p-4 transition-shadow hover:shadow-md"
      style={{ background: `color-mix(in srgb, ${tone} 8%, var(--surface))`, borderColor: `color-mix(in srgb, ${tone} 32%, transparent)` }}
    >
      <span className="block text-[11px] font-semibold" style={{ color: 'var(--muted)' }}>
        {label}
      </span>
      <strong className="mt-1 block text-2xl font-extrabold" style={{ color: tone }}>
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
    <main className="px-6 py-8" dir="rtl">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">میز کار ترجمه</h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>
            رابط جدید React — روی همان API پایتون
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ApiStatus />
          <button
            type="button"
            onClick={toggle}
            aria-pressed={theme === 'dark'}
            aria-label="تغییر حالت روشن و تاریک"
            className="grid h-10 w-10 place-items-center rounded-full border text-sm"
            style={{ background: 'var(--surface)', borderColor: 'var(--line)' }}
          >
            {theme === 'dark' ? '☀' : '◐'}
          </button>
        </div>
      </header>

      <section aria-label="خلاصهٔ وضعیت" className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="ترجمه‌های فعال" value={fa(summary.data?.active_jobs)} tone="var(--blue)" />
        <StatCard label="متوقف‌شده" value={fa(summary.data?.paused_jobs)} tone="var(--amber)" />
        <StatCard label="تکمیل‌شده" value={fa(summary.data?.completed_jobs)} tone="var(--green)" />
        <StatCard label="دارای خطا" value={fa(summary.data?.failed_jobs)} tone="var(--red)" />
      </section>

      <section className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="surface-card p-4">
          <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
            کتاب‌های کتابخانه
          </span>
          <strong className="mt-1 block text-xl font-extrabold">{fa(summary.data?.total_books)}</strong>
        </div>
        <div className="surface-card p-4">
          <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
            فضای آزاد
          </span>
          <strong className="mt-1 block text-xl font-extrabold">
            {faBytes(summary.data?.storage_free)}
          </strong>
        </div>
        <div className="surface-card p-4">
          <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
            مدل‌های در دسترس
          </span>
          <strong className="mt-1 block text-xl font-extrabold">
            {models.isPending ? '—' : fa(models.data?.items.length)}
          </strong>
        </div>
      </section>

      <section className="surface-card p-5" aria-labelledby="jobs-heading">
        <div className="mb-4 flex items-center justify-between">
          <h2 id="jobs-heading" className="text-lg font-extrabold">
            کارهای اخیر
          </h2>
          <span className="text-xs" style={{ color: 'var(--muted)' }}>
            {jobs.isPending ? 'در حال دریافت…' : `${fa(jobs.data?.items.length)} کار`}
          </span>
        </div>

        {jobs.isError ? (
          <p role="alert" className="rounded-xl border p-4 text-sm" style={{ borderColor: 'var(--red)', color: 'var(--red)' }}>
            دریافت کارها ممکن نشد. مطمئن شوید سرور پایتون روی ۸۷۶۵ اجرا است.
          </p>
        ) : (
          <ul className="grid gap-2">
            {(jobs.data?.items ?? []).slice(0, 8).map((job) => (
              <li key={job.id}>
                <Link
                  to={`/jobs/${job.id}`}
                  className="flex flex-wrap items-center gap-3 rounded-xl border p-3 transition-colors hover:border-[var(--blue)]"
                  style={{ borderColor: 'var(--line)' }}
                >
                  <span className="min-w-0 flex-1">
                    <strong className="block truncate text-sm">{job.filename}</strong>
                    <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
                      {job.filetype} · {job.source_language} → {job.target_language} ·{' '}
                      {job.progress.total ? `${fa(job.progress.completed)}/${fa(job.progress.total)}` : '—'}
                    </span>
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-bold ${BADGE_CLASS[job.status]}`}
                  >
                    {STATUS_FA[job.status]}
                  </span>
                  <span className="text-[11px] tabular-nums" style={{ color: 'var(--muted)' }}>
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
