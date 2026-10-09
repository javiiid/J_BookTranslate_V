import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { fa } from '@/lib/format'
import { calibrationApi, replaceSample } from '@/lib/calibration'
import type { Calibration, CalibrationOperation, CalibrationPatch } from '@/lib/calibration'
import { WIZARD_STEPS, canEnterStep, nextIncompleteStep, roleLabelFor, wizardStepLabel, type WizardStep } from '@/lib/calibrationSteps'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { ParallelEditor } from './CalibrationExpert'
import { StepTone } from './steps/StepTone'
import { StepModel } from './steps/StepModel'
import { StepGlossary } from './steps/StepGlossary'
import { StepReview } from './steps/StepReview'

/**
 * The simple 4-step wizard (default mode).
 * Same backend calls as expert; only the layout differs.
 * Every step is viewable; the seal action in step 4 is gated.
 */
export function CalibrationWizard({ id }: { id: string }) {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const client = useQueryClient()
  const [step, setStep] = useState<WizardStep>(0)
  const [activeId, setActiveId] = useState('')
  const [lastOperation, setLastOperation] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sync, setSync] = useState(true)
  const [tonePending, setTonePending] = useState(false)

  const query = useQuery({
    queryKey: ['calibration', id],
    queryFn: () => calibrationApi.get(id),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.busy ? 1000 : false),
  })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models })
  const session = query.data
  const opId = session?.busy ?? lastOperation
  const operation = useQuery({
    queryKey: ['calibration-operation', opId],
    queryFn: () => calibrationApi.operation(opId!),
    enabled: !!opId,
    refetchInterval: (q) => (!q.state.data || ['running', 'queued'].includes(q.state.data.status) ? 1000 : false),
  })

  const update = (value: Calibration) => client.setQueryData(['calibration', id], value)
  const fail = (e: Error) => {
    setError(e.message)
    setTonePending(false)
    void client.invalidateQueries({ queryKey: ['calibration', id] })
  }
  const action = useMutation({
    mutationFn: (work: () => Promise<Calibration>) => work(),
    onSuccess: update,
    onError: fail,
  })
  const generate = useMutation({
    mutationFn: (work: () => Promise<CalibrationOperation>) => work(),
    onSuccess: (value) => {
      setLastOperation(value.id)
      void client.invalidateQueries({ queryKey: ['calibration', id] })
    },
    onError: fail,
  })
  const start = useMutation({
    mutationFn: () => calibrationApi.start(session!),
    onSuccess: (value) => {
      void client.invalidateQueries({ queryKey: ['jobs'] })
      navigate(`/jobs/${value.id}`)
    },
    onError: fail,
  })

  useEffect(() => {
    const status = operation.data?.status
    if (status && !['running', 'queued'].includes(status)) {
      setTonePending(false)
      void client.invalidateQueries({ queryKey: ['calibration', id] })
    }
  }, [operation.data?.status, client, id])

  // Alt+Arrow keyboard navigation between steps.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return
      e.preventDefault()
      // In RTL, Alt+Right goes forward visually; keep logical order simple:
      // Alt+Left = next, Alt+Right = previous is confusing, so map both
      // directions explicitly for RTL readers.
      setStep((current) => {
        const delta = e.key === 'ArrowLeft' ? 1 : -1
        const next = Math.min(3, Math.max(0, current + delta))
        return next as WizardStep
      })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (query.isPending) {
    return (
      <>
        <h2 className="calibration-muted">{t('cal.preparingWorkshop')}</h2>
        <div className="skeleton mt-5" style={{ height: 250 }} />
      </>
    )
  }
  if (!session || query.isError) {
    return (
      <p role="alert" className="alert alert-error">
        {query.error?.message ?? t('cal.notFound')}
      </p>
    )
  }

  const current = session.samples.find((s) => s.id === activeId) ?? session.samples[0]
  const inProgress = !!session.busy || generate.isPending || ['running', 'queued'].includes(operation.data?.status ?? '')
  const disabled = inProgress || action.isPending || start.isPending || !!session.job_id
  const patch = (value: CalibrationPatch) => {
    setError(null)
    action.mutate(() => calibrationApi.edit(session, value))
  }
  const run = (ids: string[], final = true) => {
    setError(null)
    generate.mutate(() => calibrationApi.generate(session, ids, final))
  }

  const goTo = (next: WizardStep) => {
    if (canEnterStep(session, next)) setStep(next)
  }

  const selectTone = (toneId: string) => {
    if (toneId === session.profile.tone) return
    setError(null)
    setTonePending(true)
    generate.mutate(
      async () => {
        const next = await calibrationApi.edit(session, { tone: toneId as Calibration['profile']['tone'] })
        update(next)
        return calibrationApi.generate(next, current ? [current.id] : next.samples.map((s) => s.id))
      },
      {
        onError: fail,
        onSuccess: (value) => {
          setLastOperation(value.id)
          void client.invalidateQueries({ queryKey: ['calibration', id] })
        },
      },
    )
  }

  return (
    <div>
      <ol className="wizard-steps" aria-label={t('cal.wizSteps')}>
        {WIZARD_STEPS.map((item) => {
          const index = item.id as WizardStep
          const active = index === step
          return (
            <li key={item.id} aria-current={active ? 'step' : undefined}>
              <button
                type="button"
                className="wizard-step-btn"
                aria-pressed={active}
                onClick={() => goTo(index)}
              >
                <span className="wizard-step-num" aria-hidden="true">
                  {fa(index + 1)}
                </span>
                {wizardStepLabel(item.id)}
              </button>
            </li>
          )
        })}
      </ol>

      {session.warnings.length > 0 && (
        <details className="alert alert-warning">
          <summary>
            {t('cal.warnTitle', { count: fa(session.warnings.length) })}
          </summary>
          {session.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </details>
      )}
      {(error || operation.data?.error) && (
        <p role="alert" className="alert alert-error">
          {error ?? operation.data?.error}
        </p>
      )}
      {inProgress && (
        <div role="status" className="alert alert-info calibration-progress">
          <span>
            {t('cal.preparingResult')}{' '}
            {operation.data?.total ? t('cal.progressOf', { done: fa(operation.data.completed), total: fa(operation.data.total) }) : ''}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!session.busy}
            onClick={() => {
              if (session.busy) void calibrationApi.cancel(session.busy).catch(fail)
            }}
          >
            {t('cal.cancelOp')}
          </button>
        </div>
      )}

      <div className="wizard-body">
        {step === 0 && (
          <>
            <StepTone
              session={session}
              disabled={disabled}
              tonePending={tonePending || inProgress}
              onSelectTone={selectTone}
              onPatch={patch}
            />
            <section className="surface-card calibration-section" aria-labelledby="wizard-samples-heading">
              <div className="calibration-section-title">
                <div>
                  <h2 id="wizard-samples-heading">{t('cal.wizSamplesTitle')}</h2>
                  <p className="calibration-muted">{t('cal.wizSamplesHint')}</p>
                </div>
                <label className="calibration-check">
                  <input type="checkbox" checked={sync} onChange={(e) => setSync(e.target.checked)} />
                  {t('cal.sync')}
                </label>
              </div>
              <div className="sample-tabs" role="tablist" aria-label={t('cal.samplesTab')}>
                {session.samples.map((sample, i) => (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={sample.id === current?.id}
                    key={sample.id}
                    onClick={() => setActiveId(sample.id)}
                  >
                    <span>{t('cal.sampleN', { n: fa(i + 1) })}</span>
                    <small>{roleLabelFor(sample.role)}</small>
                    <span aria-label={sample.approved ? t('cal.approvedYes') : t('cal.approvedNo')}>{sample.approved ? '✓' : '○'}</span>
                  </button>
                ))}
              </div>
              {current && (
                <>
                  <label className="calibration-replace">
                    {t('cal.replaceSample')}
                    <select
                      className="field"
                      disabled={disabled}
                      value={current.id}
                      onChange={(e) => {
                        const next = e.target.value
                        patch({ selected: replaceSample(session, current.id, next) })
                        setActiveId(next)
                      }}
                    >
                      {session.candidates
                        .filter((c) => c.id === current.id || !session.samples.some((s) => s.id === c.id))
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.chapter} — {c.excerpt.slice(0, 75)}
                          </option>
                        ))}
                    </select>
                  </label>
                  {current.result?.reused && (
                    <p role="status" className="calibration-muted">
                      {t('cal.reusedNote')}
                    </p>
                  )}
                  {current.result && !current.final_verified && (
                    <p className="alert alert-warning">{t('cal.notVerifiedNote')}</p>
                  )}
                  <ParallelEditor
                    key={`${current.id}-${session.revision}`}
                    sample={current}
                    sync={sync}
                    disabled={disabled || !current.final_verified}
                    sourceLang={session.profile.from_lang}
                    glossary={session.profile.glossary}
                    onSave={(translations) =>
                      action.mutate(() => calibrationApi.feedback(session, current.id, translations))
                    }
                  />
                  <div className="calibration-actions">
                    <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => run([current.id])}>
                      {current.result ? t('cal.generateCurrent') : t('cal.translateSample')}
                    </button>
                    {session.profile.model !== session.profile.final_model && (
                      <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => run([current.id], false)}>
                        {t('cal.cheapDraft')}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={disabled || !current.final_verified || current.approved}
                      onClick={() => action.mutate(() => calibrationApi.approveSample(session, current.id))}
                    >
                      {current.approved ? t('cal.approvedSample') : t('cal.approveSample')}
                    </button>
                  </div>
                </>
              )}
            </section>
          </>
        )}

        {step === 1 && (
          <>
            <StepModel session={session} models={models.data?.items ?? []} disabled={disabled} onPatch={patch} />
            <div className="calibration-actions">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={disabled}
                onClick={() => run(session.samples.filter((s) => !s.final_verified).map((s) => s.id))}
              >
                {t('cal.generateAllFinal')}
              </button>
            </div>
          </>
        )}

        {step === 2 && (
          <StepGlossary
            terms={session.profile.glossary}
            disabled={disabled}
            proposeDisabled={inProgress}
            onSave={(terms, unlockIds) => patch({ glossary: terms, unlock_ids: unlockIds })}
            onPropose={() => {
              setError(null)
              generate.mutate(() => calibrationApi.propose(session))
            }}
          />
        )}

        {step === 3 && (
          <StepReview
            session={session}
            disabled={disabled}
            startPending={start.isPending}
            onApprove={() => action.mutate(() => calibrationApi.approve(session))}
            onStart={() => start.mutate()}
            onSaveBudget={(budget) => patch({ budget })}
          />
        )}
      </div>

      <nav className="wizard-nav" aria-label={t('cal.wizNav')}>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={step <= 0}
          onClick={() => setStep((s) => Math.max(0, s - 1) as WizardStep)}
        >
          {t('cal.prevStep')}
        </button>
        {step < 3 ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              // Suggest the next incomplete step, but respect manual choice:
              // plain next unless already at review.
              const next = Math.min(3, step + 1) as WizardStep
              void nextIncompleteStep
              goTo(next)
            }}
          >
            {t('cal.nextStep')}
          </button>
        ) : (
          <button type="button" className="btn btn-ghost" onClick={() => goTo(0)}>
            {t('cal.backToStep1')}
          </button>
        )}
      </nav>
    </div>
  )
}
