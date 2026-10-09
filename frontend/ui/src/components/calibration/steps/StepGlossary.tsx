import type { CalibrationTerm } from '@/lib/calibration'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { fa } from '@/lib/format'
import { GlossaryEditor } from '../CalibrationExpert'

interface Props {
  terms: CalibrationTerm[]
  disabled: boolean
  proposeDisabled: boolean
  onSave: (terms: CalibrationTerm[], unlockIds: string[]) => void
  onPropose: () => void
}

/**
 * Step 3: glossary. Only approved terms enter translation.
 * A locked term without an equivalent blocks progress downstream,
 * so it is surfaced here rather than at seal time.
 */
export function StepGlossary({ terms, disabled, proposeDisabled, onSave, onPropose }: Props) {
  const { t } = useLanguage()
  const lockedEmpty = terms.filter((term) => term.locked && !term.target_term.trim())
  return (
    <div>
      <p className="calibration-muted" style={{ marginBottom: 'var(--spacing-3)' }}>
        {t('cal.glossStepNote')}
      </p>
      {lockedEmpty.length > 0 && (
        <p role="alert" className="alert alert-warning">
          {t('cal.glossLockedEmpty', { count: fa(lockedEmpty.length) })}
        </p>
      )}
      <GlossaryEditor
        terms={terms}
        disabled={disabled || proposeDisabled}
        onSave={onSave}
        onPropose={onPropose}
      />
    </div>
  )
}
