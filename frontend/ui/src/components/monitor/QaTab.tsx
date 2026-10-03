import type { Job } from '@/lib/api'
import type { ChunkRow } from '@/lib/chunks'
import { fa } from '@/lib/format'
import { FlaggedList } from './VirtualChunkTable'

/**
 * QA tab.
 *
 * `quality` is a free-form score map from `app/pipeline/quality_scorer.py`, so
 * the keys are rendered as the backend spells them rather than being mapped to
 * Persian labels here. A new scorer key appears immediately instead of needing
 * a front-end change, and the Python page behaves the same way.
 */
export function QaTab({
  job,
  rows,
  isPending,
}: {
  job: Job
  rows: ChunkRow[]
  isPending: boolean
}) {
  const quality = job.quality
  const scores: [string, number][] =
    quality && typeof quality === 'object'
      ? Object.entries(quality).filter((entry): entry is [string, number] => typeof entry[1] === 'number')
      : typeof quality === 'number'
        ? [['امتیاز کلی', quality]]
        : []

  const flagged = rows.filter((row) => row.flagged)

  return (
    <div className="grid gap-[var(--spacing-4)]">
      {scores.length > 0 ? (
        <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="qa-scores-heading">
          <h2 id="qa-scores-heading" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
            امتیازها
          </h2>
          <div className="qa-grid">
            {scores.map(([label, value]) => (
              <div key={label} className="qa-item">
                <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
                <strong>{fa(Math.round(value))}</strong>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="qa-report-heading">
        <h2 id="qa-report-heading" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
          بخش‌های نیازمند بازبینی
        </h2>
        <p className="mb-[var(--spacing-3)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-muted)' }}>
          {isPending
            ? 'در حال خواندن بخش‌ها…'
            : flagged.length > 0
              ? `${fa(flagged.length)} بخش پرچم‌دار نیاز به بازبینی دارد.`
              : 'هیچ بخش پرچم‌داری وجود ندارد.'}
        </p>

        {job.qa_report ? (
          // Rendered as text, never as HTML: the report is generated text that
          // embeds model output and file paths.
          <pre className="log-box">{job.qa_report}</pre>
        ) : (
          <p className="empty">گزارش کیفیت هنوز تولید نشده است.</p>
        )}

        <FlaggedList rows={rows} />
      </section>
    </div>
  )
}
