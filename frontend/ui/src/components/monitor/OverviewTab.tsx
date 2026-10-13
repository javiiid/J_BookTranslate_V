import type { Job } from '@/lib/api'
import {
  assetLabel,
  fa,
  faBytes,
  faDate,
  faDuration,
  healthLabel,
  modeLabel,
  serverError,
  styleLabel,
} from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'

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
  const { t, lang } = useLanguage()
  const progress = job.progress ?? { completed: 0, total: 0, percent: 0 }
  // The backend can report a percent outside 0-100 after a resume, and the
  // Python page clamped it before assigning the width.
  const percent = Math.max(0, Math.min(100, progress.percent))
  const healthColor =
    job.health === 'red' ? 'var(--color-error)' : job.health === 'yellow' ? 'var(--color-warning)' : 'var(--color-success)'
  const assetEntries = Object.entries(job.asset_downloads ?? {})
  // The hero button already serves the main file; listing its 'main' asset
  // again would offer the same bytes twice under two URLs. With no hero
  // download, keep everything so the file stays reachable.
  const assetRows = job.download
    ? assetEntries.filter(([name]) => name !== 'main')
    : assetEntries

  return (
    <div className="grid gap-[var(--spacing-4)]">
      {job.error ? (
        <p
          role="alert"
          className="rounded-[var(--radius-control)] border p-[var(--spacing-4)] text-[length:var(--text-small)]"
          style={{ borderColor: 'var(--color-error)', color: 'var(--color-error)' }}
        >
          {serverError(job.error)}
        </p>
      ) : null}

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-progress">
        <div className="mb-2 flex items-center justify-between gap-[var(--spacing-4)]">
          <h2 id="ov-progress" className="text-[length:var(--text-h3)] font-extrabold">
            {t('monitor.ov.progress')}
          </h2>
          <span className="text-[length:var(--text-small)] font-bold tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
            {progress.total
              ? t('monitor.progress.ofChunks', { done: fa(progress.completed), total: fa(progress.total) })
              : t('monitor.progress.preparing')}
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t('monitor.progress.aria')}
          className="progress-track w-full"
          style={{ background: 'var(--color-surface-elevated)' }}
        >
          <div
            className="progress-fill"
            style={{ width: `${percent}%`, background: 'var(--color-primary)' }}
          />
        </div>
        <div className="mt-[var(--spacing-4)] grid grid-cols-2 gap-[var(--spacing-3)] sm:grid-cols-4">
          <Field label={t('monitor.ov.percent')} value={`${fa(percent)}${lang === 'en' ? '%' : '٪'}`} />
          <Field
            label={t('monitor.ov.health')}
            value={healthLabel(job.health)}
            tone={healthColor}
          />
          <Field
            label={t('monitor.ov.speed')}
            value={job.chunks_per_minute ? t('monitor.ov.perMinute', { rate: fa(job.chunks_per_minute) }) : t('monitor.ov.computing')}
          />
          <Field label={t('monitor.ov.eta')} value={faDuration(job.eta_seconds)} />
        </div>
      </section>

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-details">
        <h2 id="ov-details" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
          {t('monitor.ov.details')}
        </h2>
        <div className="grid grid-cols-2 gap-[var(--spacing-3)] sm:grid-cols-3">
          <Field label={t('monitor.ov.from')} value={job.source_language || '—'} />
          <Field label={t('monitor.ov.to')} value={job.target_language || '—'} />
          <Field label={t('monitor.ov.model')} value={job.model || '—'} />
          <Field label={t('monitor.ov.mode')} value={modeLabel(job.mode) || '—'} />
          <Field label={t('monitor.ov.style')} value={styleLabel(job.style) || '—'} />
          <Field label={t('monitor.ov.size')} value={faBytes(job.file_size)} />
          <Field label={t('monitor.ov.id')} value={job.id || '—'} />
          <Field label={t('monitor.ov.created')} value={faDate(job.created_at)} />
          <Field label={t('monitor.ov.started')} value={faDate(job.started_at)} />
          <Field label={t('monitor.ov.updated')} value={faDate(job.updated_at)} />
        </div>
      </section>

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="ov-actions">
        <h2 id="ov-actions" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
          {t('monitor.ov.access')}
        </h2>
        {/* Primary action first: the main file is what almost every visit
            wants. Secondary outputs get their own rows below instead of a
            bare count line that names files nobody can click. */}
        {(job.download || job.reader) && (
          <div className="flex flex-wrap gap-2">
            {job.download ? (
              <a className="btn btn-primary" href={job.download}>
                {t('monitor.ov.download')}
              </a>
            ) : null}
            {job.reader ? (
              <a className="btn btn-secondary" href={job.reader}>
                {t('monitor.ov.openReader')}
              </a>
            ) : null}
          </div>
        )}
        {assetRows.length > 0 ? (
          <div className="mt-[var(--spacing-4)]">
            <p
              className="mb-[var(--spacing-2)] text-[length:var(--text-caption)] tabular-nums"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {t('monitor.ov.outputs', { count: fa(assetRows.length) })}
            </p>
            <ul className="grid gap-2">
              {assetRows.map(([name, url]) => (
                <li key={name}>
                  <a
                    className="surface-card flex min-w-0 items-center justify-between gap-3 p-3"
                    href={url}
                  >
                    <strong
                      className="min-w-0 truncate text-[length:var(--text-small)]"
                      title={assetLabel(name)}
                    >
                      {assetLabel(name)}
                    </strong>
                    <span className="btn btn-ghost shrink-0">
                      {t('monitor.ov.downloadAsset')}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {!job.download && !job.reader && assetRows.length === 0 ? (
          <span className="text-[length:var(--text-label)]" style={{ color: 'var(--color-text-muted)' }}>
            {t('monitor.ov.noOutputs')}
          </span>
        ) : null}
      </section>
    </div>
  )
}

// Re-exported for the tabs that render a status chip.
