import { Link } from 'react-router-dom'
import { fa } from '@/lib/format'
import { canSeal } from '@/lib/calibration'
import type { Calibration } from '@/lib/calibration'
import { reviewChecks } from '@/lib/calibrationSteps'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { BudgetEditor, CostPanel } from '../CalibrationExpert'
import type { CalibrationBudget } from '@/lib/calibration'

interface Props {
  session: Calibration
  disabled: boolean
  startPending: boolean
  onApprove: () => void
  onStart: () => void
  onSaveBudget: (budget: CalibrationBudget) => void
}

/**
 * Step 4: review. The seal button is never just disabled: each
 * failing check is named, so the reader knows what to do next.
 */
export function StepReview({ session, disabled, startPending, onApprove, onStart, onSaveBudget }: Props) {
  const { t } = useLanguage()
  const checks = reviewChecks(session)
  const sealable = canSeal(session)
  return (
    <div className="grid gap-4">
      <section className="surface-card calibration-section" aria-labelledby="wizard-review-heading">
        <h2 id="wizard-review-heading">{t('cal.reviewStep')}</h2>
        <ul className="grid gap-2" style={{ listStyle: 'none', padding: 0, marginBlock: 'var(--spacing-3)' }}>
          {checks.map((check) => (
            <li key={check.key} className={check.ok ? 'alert alert-info' : 'alert alert-warning'}>
              <span aria-hidden="true">{check.ok ? '✓ ' : '○ '}</span>
              {check.label}
            </li>
          ))}
        </ul>
        {!sealable && !session.job_id && (
          <p className="calibration-muted">
            {t('cal.sealHint')}
          </p>
        )}
        <div className="calibration-actions">
          {session.job_id ? (
            <Link className="btn btn-primary" to={`/jobs/${session.job_id}`}>
              {t('cal.viewTranslation')}
            </Link>
          ) : session.approved_profile_hash ? (
            <button type="button" className="btn btn-primary" disabled={disabled || startPending} onClick={onStart}>
              {startPending ? t('cal.starting') : t('cal.startWithQuote')}
            </button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={disabled || !sealable} onClick={onApprove}>
              {t('cal.seal')}
            </button>
          )}
        </div>
        <p className="calibration-muted">
          {t('cal.approvedCount', { done: fa(session.samples.filter((s) => s.approved).length), total: fa(session.samples.length) })}
          {' '}{t('cal.lockNote1')}
          {' '}{t('cal.lockNote2')}
        </p>
      </section>
      <CostPanel session={session} />
      <BudgetEditor
        key={`budget-${session.revision}`}
        value={session.budget}
        disabled={disabled}
        configured={session.quote.pricing === 'configured'}
        onSave={onSaveBudget}
      />
    </div>
  )
}
