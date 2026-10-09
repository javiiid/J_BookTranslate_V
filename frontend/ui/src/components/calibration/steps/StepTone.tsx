import type { Calibration, CalibrationPatch } from '@/lib/calibration'
import { toneDescription, toneLabel } from '@/lib/calibrationSteps.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { Instructions } from '../CalibrationExpert'

interface Props {
  session: Calibration
  disabled: boolean
  onSelectTone: (toneId: string) => void
  onPatch: (patch: CalibrationPatch) => void
  tonePending: boolean
}

/**
 * Step 1: tone. Choosing a tone saves it and regenerates the open
 * sample with the final model, so the reader hears the voice
 * on real text before anything else.
 */
export function StepTone({ session, disabled, onSelectTone, onPatch, tonePending }: Props) {
  const { t } = useLanguage()
  return (
    <section className="surface-card calibration-section" aria-labelledby="wizard-tone-heading">
      <h2 id="wizard-tone-heading">{t('cal.toneStep')}</h2>
      <p className="calibration-muted">
        {t('cal.toneStepHint')}
      </p>
      {tonePending && (
        <p role="status" className="alert alert-info">
          {t('cal.toneGenerating')}
        </p>
      )}
      <div className="tone-matrix" role="group" aria-label={t('cal.toneGroup')}>
        {session.tones.map((tone) => (
          <button
            type="button"
            key={tone.id}
            disabled={disabled || tonePending}
            className="tone-choice"
            aria-pressed={session.profile.tone === tone.id}
            onClick={() => {
              if (tone.id !== session.profile.tone) onSelectTone(tone.id)
            }}
          >
            <strong>{toneLabel(tone.id, tone.label)}</strong>
            <span>{toneDescription(tone.id, tone.description)}</span>
          </button>
        ))}
      </div>
      <Instructions
        key={`instructions-${session.revision}`}
        value={session.profile.instructions}
        disabled={disabled}
        onSave={(value) => onPatch({ instructions: value })}
      />
    </section>
  )
}
