import type { JobEvent } from '@/lib/api'
import { faDate } from '@/lib/format'

/** Levels the Python page treats as problems rather than progress. */
const TONE: Record<string, string> = {
  error: 'var(--color-error)',
  warn: 'var(--color-warning)',
  warning: 'var(--color-warning)',
}

export function LogsTab({
  events,
  isPending,
  isError,
  onRetry,
}: {
  events: JobEvent[] | undefined
  isPending: boolean
  isError: boolean
  onRetry: () => void
}) {
  if (isError) {
    return (
      <div className="surface-card p-[var(--spacing-5)]">
        <p role="alert" className="alert alert-error">
          دریافت لاگ‌ها ممکن نشد.
        </p>
        <button type="button" className="btn btn-secondary" onClick={onRetry} style={{ marginTop: 12 }}>
          تلاش دوباره
        </button>
      </div>
    )
  }

  if (isPending) {
    return (
      <div className="surface-card p-[var(--spacing-5)]">
        <div className="skeleton" style={{ height: 220 }} />
      </div>
    )
  }

  const items = events ?? []
  if (items.length === 0) {
    return <div className="surface-card empty">هنوز رویدادی ثبت نشده است.</div>
  }

  return (
    <div className="surface-card p-[var(--spacing-5)]">
      {/* Newest first: the reason someone opens this tab is to see what just
          broke, not what happened an hour ago. */}
      <ol className="timeline" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 8 }}>
        {items.map((event, index) => (
          <li
            key={`${event.timestamp}-${index}`}
            className="tl-row"
            style={{ display: 'grid', gap: 4 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span
                className="badge"
                style={{
                  color: TONE[String(event.level).toLowerCase()] ?? 'var(--color-text-muted)',
                  borderColor: 'var(--color-border)',
                }}
              >
                {event.level}
              </span>
              <strong className="text-[length:var(--text-label)]">{event.event}</strong>
              <span className="ms-auto text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
                {faDate(event.timestamp)}
              </span>
            </div>
            <p className="m-0 text-[length:var(--text-small)] leading-7" style={{ color: 'var(--color-text-primary)' }}>
              {event.message}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}
