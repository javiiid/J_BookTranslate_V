import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { calibrationApi } from '@/lib/calibration'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { useCalibrationMode } from '@/hooks/useCalibrationMode'
import { CalibrationExpert } from '@/components/calibration/CalibrationExpert'
import { CalibrationWizard } from '@/components/calibration/CalibrationWizard'
import '@/styles/calibration.css'

export function CalibrationPage() {
  const { t, dir } = useLanguage()
  const { id = '' } = useParams()
  const { mode, setMode, isSimple } = useCalibrationMode()
  // Light header query so the title/pill render even before the
  // wizard/expert body loads its own full session. Cached by key.
  const header = useQuery({
    queryKey: ['calibration', id],
    queryFn: () => calibrationApi.get(id),
    enabled: !!id,
    staleTime: 5_000,
  })
  const session = header.data

  if (!id) {
    return (
      <main className="page" dir={dir}>
        <p role="alert" className="alert alert-error">
          {t('cal.notFound')}
        </p>
        <Link className="btn btn-secondary mt-4" to="/workspace">
          {t('cal.backToAdd')}
        </Link>
      </main>
    )
  }

  return (
    <main className="page calibration-page" dir={dir}>
      <header className="calibration-header">
        <div>
          <Link to="/workspace" className="calibration-back">
            ← {t('cal.back')}
          </Link>
          <h1>{t('cal.title')}</h1>
          <p className="calibration-muted">
            {session ? t('cal.subtitle', { filename: session.filename, count: fa(session.unit_count) }) : t('cal.loading')}
          </p>
        </div>
        <div className="calibration-header-side">
          <span className="calibration-pill">
            {session?.job_id ? t('cal.pillLocked') : session?.approved_profile_hash ? t('cal.pillReady') : t('cal.pillWorkshop')}
          </span>
          <div className="mode-toggle" role="group" aria-label={t('cal.modeLabel')}>
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={isSimple}
              onClick={() => setMode('simple')}
              style={isSimple ? { background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' } : undefined}
            >
              {t('cal.simple')}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={!isSimple}
              onClick={() => setMode('expert')}
              style={!isSimple ? { background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' } : undefined}
            >
              {t('cal.expert')}
            </button>
          </div>
        </div>
      </header>
      <p className="calibration-muted">
        {mode === 'simple' ? t('cal.simpleHint') : t('cal.expertHint')}
      </p>

      {isSimple ? <CalibrationWizard id={id} /> : <CalibrationExpert id={id} />}
    </main>
  )
}
