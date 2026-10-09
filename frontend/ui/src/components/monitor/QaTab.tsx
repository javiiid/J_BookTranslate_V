import type { Job } from '@/lib/api'
import type { ChunkRow } from '@/lib/chunks'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
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
  const { t } = useLanguage()
  const scores: [string, number][] =
    quality && typeof quality === 'object'
      ? Object.entries(quality).filter((entry): entry is [string, number] => typeof entry[1] === 'number')
      : typeof quality === 'number'
        ? [[t('monitor.qa.overall'), quality]]
        : []

  const flagged = rows.filter((row) => row.flagged)

  return (
    <div className="grid gap-[var(--spacing-4)]">
      {scores.length > 0 ? (
        <section className="surface-card p-[var(--spacing-5)]" aria-labelledby="qa-scores-heading">
          <h2 id="qa-scores-heading" className="mb-[var(--spacing-3)] text-[length:var(--text-h3)] font-extrabold">
            {t('monitor.qa.scores')}
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
          {t('monitor.qa.reviewTitle')}
        </h2>
        <p className="mb-[var(--spacing-3)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-muted)' }}>
          {isPending
            ? t('monitor.qa.reading')
            : flagged.length > 0
              ? t('monitor.qa.flaggedSome', { n: fa(flagged.length) })
              : t('monitor.qa.flaggedNone')}
        </p>

        {job.qa_report ? (
          // Rendered as text, never as HTML: the report is generated text that
          // embeds model output and file paths.
          <pre className="log-box">{job.qa_report}</pre>
        ) : (
          <p className="empty">{t('monitor.qa.noReport')}</p>
        )}

        <FlaggedList rows={rows} />
      </section>
    </div>
  )
}
