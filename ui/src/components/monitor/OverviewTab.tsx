import type { Job } from '@/lib/api'
import {
  ASSET_FA,
  HEALTH_FA,
  MODE_FA,
  STATUS_FA,
  STYLE_FA,
  fa,
  faBytes,
  faDate,
  faDuration,
} from '@/lib/format'

function Field({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="surface-card p-[var(--spacing-3)]">
      <span className="data-label">
        {label}
      </span>
      <strong className="mt-[var(--spacing-1)] block truncate text-[length:var(--text-small)]" style={tone ? { color: tone } : undefined} title={value}>
        {value}
      </strong>
    </div>
  )
}

export function OverviewTab({ job }: { job: Job }) {
  const progress = job.progress ?? { completed: 0, total: 0, percent: 0 }
  // The backend can report a percent outside 0-100 after a resume, and the
  // Python page clamped it before assigning the width.
  const percent = Math.max(0, Math.min(100, progress.percent))
  const healthColor =
    job.health === 'red' ? 'var(--color-error)' : job.health === 'yellow' ? 'var(--color-warning)' : 'var(--color-success)'

  return (
    <div className="grid gap-[var(--spacing-4)]">
      {job.error ? (
        <p
          role="alert"
          className="rounded-[var(--radius-control)] border p-[var(--spacing-4)] text-[length:var(--text-small)]"
          style={{ borderColor: 'var(--color-error)', color: 'var(--color-error)' }}
        >
          {job.error}
        </p>
      ) : null}

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-progress">
        <div className="mb-2 flex items-center justify-between gap-[var(--spacing-4)]">
          <h2 id="ov-progress" className="text-[length:var(--text-h3)] font-extrabold">
            پیشرفت
          </h2>
          <span className="text-[length:var(--text-small)] font-bold tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
            {progress.total
              ? `${fa(progress.completed)} از ${fa(progress.total)} بخش ترجمه شده`
              : 'در حال آماده‌سازی کتاب…'}
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="درصد پیشرفت ترجمه"
          className="progress-track w-full"
          style={{ background: 'var(--color-surface-elevated)' }}
        >
          <div
            className="progress-fill"
            style={{ width: `${percent}%`, background: 'var(--color-primary)' }}
          />
        </div>
        <div className="mt-[var(--spacing-4)] grid grid-cols-2 gap-[var(--spacing-3)] sm:grid-cols-4">
          <Field label="درصد" value={`${fa(percent)}٪`} />
          <Field
            label="سلامت"
            value={HEALTH_FA[job.health] ?? '—'}
            tone={healthColor}
          />
          <Field
            label="سرعت"
            value={job.chunks_per_minute ? `${fa(job.chunks_per_minute)} بخش/دقیقه` : 'در حال محاسبه'}
          />
          <Field label="زمان باقی‌مانده" value={faDuration(job.eta_seconds)} />
        </div>
      </section>

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-details">
        <h2 id="ov-details" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
          جزئیات
        </h2>
        <div className="grid grid-cols-2 gap-[var(--spacing-3)] sm:grid-cols-3">
          <Field label="زبان مبدأ" value={job.source_language || '—'} />
          <Field label="زبان مقصد" value={job.target_language || '—'} />
          <Field label="مدل" value={job.model || '—'} />
          <Field label="حالت" value={MODE_FA[job.mode] ?? job.mode ?? '—'} />
          <Field label="سبک" value={STYLE_FA[job.style] ?? job.style ?? '—'} />
          <Field label="حجم فایل" value={faBytes(job.file_size)} />
          <Field label="شناسه" value={job.id || '—'} />
          <Field label="ساخته‌شده" value={faDate(job.created_at)} />
          <Field label="شروع" value={faDate(job.started_at)} />
          <Field label="آخرین تغییر" value={faDate(job.updated_at)} />
        </div>
      </section>

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-actions">
        <h2 id="ov-actions" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
          خروجی و دسترسی
        </h2>
        <div className="flex flex-wrap gap-2">
          {job.download ? (
            <a className="btn btn-secondary" href={job.download}>
              دانلود خروجی اصلی
            </a>
          ) : null}
          {job.reader ? (
            <a className="btn btn-secondary" href={job.reader}>
              باز کردن در Reader
            </a>
          ) : null}
          {!job.download && !job.reader ? (
            <span className="text-[length:var(--text-label)]" style={{ color: 'var(--color-text-muted)' }}>
              هنوز خروجی قابل دانلودی ساخته نشده است.
            </span>
          ) : null}
        </div>
        {Object.keys(job.assets ?? {}).length > 0 ? (
          <p className="mt-[var(--spacing-3)] text-[length:var(--text-label)]" style={{ color: 'var(--color-text-muted)' }}>
            {fa(Object.keys(job.assets).length)} خروجی:{' '}
            {Object.keys(job.assets)
              .map((name) => ASSET_FA[name] ?? name)
              .join('، ')}
          </p>
        ) : null}
      </section>
    </div>
  )
}

// Re-exported for the tabs that render a status chip.
export { STATUS_FA }
