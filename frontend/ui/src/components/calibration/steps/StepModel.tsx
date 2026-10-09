import type { Calibration, CalibrationPatch } from '@/lib/calibration'
import { useLanguage } from '@/i18n/useLanguage.ts'

interface ModelItem {
  id: string
}

interface Props {
  session: Calibration
  models: ModelItem[]
  disabled: boolean
  onPatch: (patch: CalibrationPatch) => void
}

/**
 * Step 2: models. Draft is for comparison; the final model is what
 * the book is translated with. When they differ, every sample must
 * be verified against the final model before sealing.
 */
export function StepModel({ session, models, disabled, onPatch }: Props) {
  const { t } = useLanguage()
  const differs = session.profile.model !== session.profile.final_model
  return (
    <section className="surface-card calibration-section" aria-labelledby="wizard-model-heading">
      <h2 id="wizard-model-heading">{t('cal.modelStep')}</h2>
      <p className="calibration-muted">
        {t('cal.modelStepHint')}
      </p>
      <div className="calibration-models">
        <label>
          {t('cal.draftModel')}
          <select
            className="field"
            value={session.profile.model}
            disabled={disabled}
            onChange={(e) => onPatch({ model: e.target.value })}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('cal.finalModel')}
          <select
            className="field"
            value={session.profile.final_model}
            disabled={disabled}
            onChange={(e) => onPatch({ final_model: e.target.value })}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>
        </label>
      </div>
      {differs && (
        <p role="note" className="alert alert-warning">
          {t('cal.modelsDifferWarn')}
        </p>
      )}
    </section>
  )
}
