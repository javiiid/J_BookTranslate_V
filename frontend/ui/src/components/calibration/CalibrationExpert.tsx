import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { fa } from '@/lib/format'
import { calibrationApi, canSeal, formatCost, replaceSample } from '@/lib/calibration'
import { roleLabelFor, toneDescription, toneLabel } from '@/lib/calibrationSteps'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { diffSummary, wordDiff } from '@/lib/slotDiff'
import { slotSuggestions } from '@/lib/slotSuggest'
import type { Calibration, CalibrationBudget, CalibrationOperation, CalibrationPatch, CalibrationSample, CalibrationTerm, TextSlot } from '@/lib/calibration'
import '@/styles/calibration.css'

/** Role labels live in lib/calibrationSteps so this component module exports components only (Fast Refresh). */

/**
 * The full workshop view (expert mode).
 * Byte-for-byte the previous CalibrationPage; kept intact so experts
 * lose nothing when the wizard becomes the default.
 */
export function CalibrationExpert({ id }: { id: string }) {
  const { t, dir } = useLanguage()
  const navigate = useNavigate()
  const client = useQueryClient()
  const [activeId, setActiveId] = useState('')
  const [lastOperation, setLastOperation] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sync, setSync] = useState(true)
  const query = useQuery({ queryKey: ['calibration', id], queryFn: () => calibrationApi.get(id), enabled: !!id,
    refetchInterval: q => q.state.data?.busy ? 1000 : false })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models })
  const session = query.data
  const opId = session?.busy ?? lastOperation
  const operation = useQuery({ queryKey: ['calibration-operation', opId], queryFn: () => calibrationApi.operation(opId!), enabled: !!opId,
    refetchInterval: q => !q.state.data || ['running', 'queued'].includes(q.state.data.status) ? 1000 : false })
  const update = (value: Calibration) => client.setQueryData(['calibration', id], value)
  const fail = (e: Error) => { setError(e.message); void client.invalidateQueries({ queryKey: ['calibration', id] }) }
  const action = useMutation({ mutationFn: (work: () => Promise<Calibration>) => work(), onSuccess: update, onError: fail })
  const generate = useMutation({ mutationFn: (work: () => Promise<CalibrationOperation>) => work(), onSuccess: value => {
    setLastOperation(value.id)
    void client.invalidateQueries({ queryKey: ['calibration', id] })
  }, onError: fail })
  const start = useMutation({ mutationFn: () => calibrationApi.start(session!), onSuccess: value => {
    void client.invalidateQueries({ queryKey: ['jobs'] }); navigate(`/jobs/${value.id}`)
  }, onError: fail })

  useEffect(() => {
    const status = operation.data?.status
    if (status && !['running', 'queued'].includes(status)) {
      void client.invalidateQueries({ queryKey: ['calibration', id] })
    }
  }, [operation.data?.status, client, id])

  if (query.isPending) return <main className="page" dir={dir}><h1>{t('cal.preparingWorkshop')}</h1><div className="skeleton mt-5" style={{ height: 250 }} /></main>
  if (!session || query.isError) return <main className="page" dir={dir}><p role="alert" className="alert alert-error">{query.error?.message ?? t('cal.notFound')}</p><Link className="btn btn-secondary mt-4" to="/workspace">{t('cal.backToAdd')}</Link></main>

  const current = session.samples.find(s => s.id === activeId) ?? session.samples[0]
  const inProgress = !!session.busy || generate.isPending || ['running', 'queued'].includes(operation.data?.status ?? '')
  const disabled = inProgress || action.isPending || start.isPending || !!session.job_id
  const patch = (value: CalibrationPatch) => { setError(null); action.mutate(() => calibrationApi.edit(session, value)) }
  const run = (ids: string[], final = true) => { setError(null); generate.mutate(() => calibrationApi.generate(session, ids, final)) }

  return <div>
    <ol className="calibration-steps" aria-label={t('cal.legacySteps')}>
      {[t('cal.legacyStep1'), t('cal.legacyStep2'), t('cal.legacyStep3'), t('cal.legacyStep4')].map((label, i) => <li key={label} aria-current={i === (session.job_id ? 3 : session.approved_profile_hash ? 2 : 1) ? 'step' : undefined}><span>{fa(i + 1)}</span>{label}</li>)}
    </ol>
    {session.warnings.length > 0 && <details className="alert alert-warning"><summary>{t('cal.warnTitle', { count: fa(session.warnings.length) })}</summary>{session.warnings.map((w, i) => <p key={i}>{w}</p>)}</details>}
    {(error || operation.data?.error) && <p role="alert" className="alert alert-error">{error ?? operation.data?.error}</p>}
    {inProgress && <div role="status" className="alert alert-info calibration-progress"><span>{t('cal.preparingResult')} {operation.data?.total ? t('cal.progressOf', { done: fa(operation.data.completed), total: fa(operation.data.total) }) : ''}</span><button type="button" className="btn btn-ghost" disabled={!session.busy} onClick={() => { if (session.busy) void calibrationApi.cancel(session.busy).catch(fail) }}>{t('cal.cancelOp')}</button></div>}

    <div className="calibration-layout">
      <div className="calibration-main">
        <section className="surface-card calibration-section" aria-labelledby="tone-heading">
          <div className="calibration-section-title"><div><h2 id="tone-heading">{t('cal.toneTitle')}</h2><p className="calibration-muted">{t('cal.toneHint')}</p></div></div>
          <div className="tone-matrix" role="group" aria-label={t('cal.toneGroup')}>{session.tones.map(tone => <button type="button" key={tone.id} disabled={disabled} className="tone-choice" aria-pressed={session.profile.tone === tone.id} onClick={() => {
            if (tone.id === session.profile.tone) return
            setError(null)
            generate.mutate(async () => {
              const next = await calibrationApi.edit(session, { tone: tone.id }); update(next)
              return calibrationApi.generate(next, current ? [current.id] : next.samples.map(s => s.id))
            })
          }}><strong>{toneLabel(tone.id, tone.label)}</strong><span>{toneDescription(tone.id, tone.description)}</span></button>)}</div>
          <div className="calibration-models">
            <label>{t('cal.draftModel')}<select className="field" value={session.profile.model} disabled={disabled} onChange={e => patch({ model: e.target.value })}>{(models.data?.items ?? []).map(m => <option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
            <label>{t('cal.finalModel')}<select className="field" value={session.profile.final_model} disabled={disabled} onChange={e => patch({ final_model: e.target.value })}>{(models.data?.items ?? []).map(m => <option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
          </div>
          {session.profile.model !== session.profile.final_model && <p className="calibration-muted">{t('cal.modelsDiffer')}</p>}
          <Instructions key={`instructions-${session.revision}`} value={session.profile.instructions} disabled={disabled} onSave={value => patch({ instructions: value })} />
        </section>

        <section className="surface-card calibration-section" aria-labelledby="samples-heading">
          <div className="calibration-section-title"><div><h2 id="samples-heading">{t('cal.samplesTitle')}</h2><p className="calibration-muted">{t('cal.samplesHint')}</p></div><label className="calibration-check"><input type="checkbox" checked={sync} onChange={e => setSync(e.target.checked)} />{t('cal.sync')}</label></div>
          <div className="sample-tabs" role="tablist" aria-label={t('cal.samplesTab')}>{session.samples.map((sample, i) => <button type="button" role="tab" aria-selected={sample.id === current?.id} key={sample.id} onClick={() => setActiveId(sample.id)}><span>{t('cal.sampleN', { n: fa(i + 1) })}</span><small>{roleLabelFor(sample.role)}</small><span aria-label={sample.approved ? t('cal.approvedYes') : t('cal.approvedNo')}>{sample.approved ? '✓' : '○'}</span></button>)}</div>
          {current && <>
            <label className="calibration-replace">{t('cal.replaceSample')}<select className="field" disabled={disabled} value={current.id} onChange={e => { const next = e.target.value; patch({ selected: replaceSample(session, current.id, next) }); setActiveId(next) }}>{session.candidates.filter(c => c.id === current.id || !session.samples.some(s => s.id === c.id)).map(c => <option key={c.id} value={c.id}>{c.chapter} — {c.excerpt.slice(0, 75)}</option>)}</select></label>
            {current.result?.reused && <p role="status" className="calibration-muted">{t('cal.reusedNote')}</p>}
            {current.result && !current.final_verified && <p className="alert alert-warning">{t('cal.notVerifiedNote')}</p>}
            <ParallelEditor key={`${current.id}-${session.revision}`} sample={current} sync={sync} disabled={disabled || !current.final_verified} sourceLang={session.profile.from_lang} glossary={session.profile.glossary} onSave={translations => action.mutate(() => calibrationApi.feedback(session, current.id, translations))} />
            <div className="calibration-actions">
              <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => run([current.id])}>{current.result ? t('cal.generateCurrent') : t('cal.translateSample')}</button>
              {session.profile.model !== session.profile.final_model && <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => run([current.id], false)}>{t('cal.cheapDraft')}</button>}
              <button type="button" className="btn btn-primary" disabled={disabled || !current.final_verified || current.approved} onClick={() => action.mutate(() => calibrationApi.approveSample(session, current.id))}>{current.approved ? t('cal.approvedSample') : t('cal.approveSample')}</button>
            </div>
          </>}
          <button type="button" className="btn btn-ghost mt-3" disabled={disabled} onClick={() => run(session.samples.filter(s => !s.final_verified).map(s => s.id))}>{t('cal.generateAll')}</button>
        </section>

        <GlossaryEditor key={`glossary-${session.revision}`} terms={session.profile.glossary} disabled={disabled}
          onSave={(terms, unlockIds) => patch({ glossary: terms, unlock_ids: unlockIds })}
          onPropose={() => { setError(null); generate.mutate(() => calibrationApi.propose(session)) }} />
      </div>

      <aside className="calibration-sidebar">
        <CostPanel session={session} />
        <BudgetEditor key={`budget-${session.revision}`} value={session.budget} disabled={disabled} configured={session.quote.pricing === 'configured'} onSave={budget => patch({ budget })} />
        <section className="surface-card calibration-section calibration-approval">
          <h2>{t('cal.readyTitle')}</h2><p>{t('cal.approvedCount', { done: fa(session.samples.filter(s => s.approved).length), total: fa(session.samples.length) })}</p>
          <p className="calibration-muted">{t('cal.lockNote1')}</p>
          <p className="calibration-muted">{t('cal.lockNote2')}</p>
          {session.job_id ? <Link className="btn btn-primary" to={`/jobs/${session.job_id}`}>{t('cal.viewTranslation')}</Link> : session.approved_profile_hash ? <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => start.mutate()}>{t('cal.startWithQuote')}</button> : <button type="button" className="btn btn-primary" disabled={disabled || !canSeal(session)} onClick={() => action.mutate(() => calibrationApi.approve(session))}>{t('cal.seal')}</button>}
        </section>
      </aside>
    </div>
  </div>
}

export function Instructions({ value, disabled, onSave }: { value: string; disabled: boolean; onSave: (value: string) => void }) {
  const { t } = useLanguage()
  const [draft, setDraft] = useState(value)
  return <details className="calibration-instructions"><summary>{t('cal.instTitle')}</summary><label>{t('cal.instLabel')}<textarea className="field" rows={3} maxLength={2000} value={draft} disabled={disabled} placeholder={t('cal.instPh')} onChange={e => setDraft(e.target.value)} /></label><button className="btn btn-secondary" type="button" disabled={disabled || draft === value} onClick={() => onSave(draft)}>{t('cal.instSave')}</button><p className="calibration-muted">{t('cal.instNote')}</p></details>
}

export function ParallelEditor({ sample, sync, disabled, sourceLang, glossary, onSave }: { sample: CalibrationSample; sync: boolean; disabled: boolean; sourceLang: string; glossary?: CalibrationTerm[]; onSave: (slots: TextSlot[]) => void }) {
  const { t } = useLanguage()
  const [draft, setDraft] = useState(sample.result?.translations ?? [])
  const [showDiff, setShowDiff] = useState(true)
  // The model draft as first seen: diffs and reverts compare against this,
  // not against the live server value. The parent remounts per revision
  // (key includes sample id + revision), so a fresh generation refreshes it.
  // State rather than a ref: it never changes after mount, and refs must
  // not be read during render.
  const [baseline] = useState(() => new Map((sample.result?.translations ?? []).map((s) => [s.id, s.text])))
  const source = useRef<HTMLDivElement>(null)
  const target = useRef<HTMLDivElement>(null)
  const moving = useRef(false)
  const raf = useRef(0)
  const fields = useRef(new Map<string, HTMLTextAreaElement>())
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 640px)').matches,
  )
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(max-width: 640px)')
    const onChange = () => setNarrow(query.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  useEffect(() => () => cancelAnimationFrame(raf.current), [])

  const dirty = JSON.stringify(draft) !== JSON.stringify(sample.result?.translations ?? [])
  // Stacked panes on a phone have no shared axis; syncing them would fight the reader.
  const effectiveSync = sync && !narrow

  function align(from: HTMLDivElement, to: HTMLDivElement | null) {
    if (!effectiveSync || !to || moving.current) return
    // Never yank the pane being typed in: the caret position is the reader's.
    const active = document.activeElement
    if (active && active.tagName === 'TEXTAREA' && to.contains(active)) return
    const blocks = [...from.querySelectorAll<HTMLElement>('[data-slot]')]
    const top = from.getBoundingClientRect().top
    const anchor = blocks.find((b) => b.getBoundingClientRect().bottom > top + 4)
    const matching = anchor
      ? [...to.querySelectorAll<HTMLElement>('[data-slot]')].find((b) => b.dataset.slot === anchor.dataset.slot)
      : undefined
    moving.current = true
    if (anchor && matching) {
      const fraction = (top - anchor.getBoundingClientRect().top) / Math.max(1, anchor.offsetHeight)
      to.scrollTop += matching.getBoundingClientRect().top - to.getBoundingClientRect().top + fraction * matching.offsetHeight
    } else {
      // No shared anchor (uneven heights after edits): fall back to position ratio.
      const fromRange = from.scrollHeight - from.clientHeight
      const toRange = to.scrollHeight - to.clientHeight
      if (fromRange > 0 && toRange > 0) to.scrollTop = (from.scrollTop / fromRange) * toRange
    }
    requestAnimationFrame(() => {
      moving.current = false
    })
  }
  function scheduleAlign(from: HTMLDivElement, to: HTMLDivElement | null) {
    if (!effectiveSync) return
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(() => align(from, to))
  }

  const order = draft.map((s) => s.id)
  const focusSlot = (id: string) => {
    const el = fields.current.get(id)
    if (!el) return
    el.focus()
    el.scrollIntoView({ block: 'nearest' })
  }
  const stepFocus = (id: string, delta: -1 | 1) => {
    const index = order.indexOf(id)
    const next = order[Math.min(order.length - 1, Math.max(0, index + delta))]
    if (next && next !== id) focusSlot(next)
  }

  const sourceById = new Map(sample.slots.map((s) => [s.id, s.text]))
  const revertSlot = (id: string) => {
    const base = baseline.get(id)
    if (base === undefined) return
    setDraft((old) => old.map((s) => (s.id === id ? { ...s, text: base } : s)))
  }
  const revertAll = () => {
    if (!window.confirm(t('cal.revertConfirm'))) return
    setDraft((old) => old.map((s) => ({ ...s, text: baseline.get(s.id) ?? s.text })))
  }
  const insertSuggestion = (id: string, text: string) => {
    const el = fields.current.get(id)
    const current = el?.value ?? draft.find((s) => s.id === id)?.text ?? ''
    const start = el?.selectionStart ?? current.length
    const end = el?.selectionEnd ?? current.length
    const next = current.slice(0, start) + text + current.slice(end)
    setDraft((old) => old.map((s) => (s.id === id ? { ...s, text: next } : s)))
    requestAnimationFrame(() => {
      const node = fields.current.get(id)
      if (!node) return
      node.focus()
      const pos = start + text.length
      node.setSelectionRange(pos, pos)
    })
  }

  if (!sample.result) {
    return (
      <>
        <div className="parallel-labels">
          <strong>{t('cal.srcPane')}</strong>
          <strong>{t('cal.trPane')}</strong>
        </div>
        <div className="parallel-editor" dir="ltr">
          <div ref={source} className="parallel-pane" lang={sourceLang.toLowerCase()} dir={['FA', 'AR', 'HE'].includes(sourceLang) ? 'rtl' : 'ltr'} onScroll={(e) => scheduleAlign(e.currentTarget, target.current)}>
            {sample.slots.map((slot) => (
              <p data-slot={slot.id} key={slot.id}>
                {slot.text}
              </p>
            ))}
          </div>
          <div className="parallel-pane" dir="rtl" lang="fa">
            <div className="calibration-empty">
              <strong>{t('cal.noResult')}</strong>
              <p>{t('cal.noResultHint')}</p>
            </div>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="parallel-labels">
        <strong>{t('cal.srcPane')}</strong>
        <strong>{t('cal.trPane')} {sample.result?.origin === 'human_edit' ? t('cal.trEdited') : ''}</strong>
      </div>
      <div className="slot-toolbar">
        <label className="calibration-check">
          <input type="checkbox" checked={showDiff} onChange={(e) => setShowDiff(e.target.checked)} />
          {t('cal.showDiff')}
        </label>
        <button type="button" className="btn btn-ghost" disabled={disabled} onClick={revertAll}>
          {t('cal.revertAll')}
        </button>
        <span className="calibration-muted">{t('cal.kbdHint')}</span>
      </div>
      {narrow && sync && <p className="calibration-muted">{t('cal.narrowSyncOff')}</p>}
      <div className="parallel-editor" dir="ltr">
        <div ref={source} className="parallel-pane" lang={sourceLang.toLowerCase()} dir={['FA', 'AR', 'HE'].includes(sourceLang) ? 'rtl' : 'ltr'} onScroll={(e) => scheduleAlign(e.currentTarget, target.current)}>
          {sample.slots.map((slot) => (
            <p data-slot={slot.id} key={slot.id}>
              {slot.text}
            </p>
          ))}
        </div>
        <div ref={target} className="parallel-pane" dir="rtl" lang="fa" onScroll={(e) => scheduleAlign(e.currentTarget, source.current)}>
          {draft.map((slot, index) => {
            const base = baseline.get(slot.id) ?? ''
            const changed = base !== slot.text
            const parts = showDiff && changed ? wordDiff(base, slot.text) : []
            const { added, removed } = diffSummary(parts)
            const suggestions = slotSuggestions(sourceById.get(slot.id) ?? '', glossary ?? [])
            return (
              <div data-slot={slot.id} key={slot.id} className="slot-block">
                <textarea
                  ref={(node) => {
                    if (node) fields.current.set(slot.id, node)
                    else fields.current.delete(slot.id)
                  }}
                  aria-label={t('cal.editSlot', { n: fa(index + 1) })}
                  className="sample-text"
                  rows={Math.max(2, Math.min(12, Math.ceil(slot.text.length / 60)))}
                  disabled={disabled}
                  value={slot.text}
                  onChange={(e) => setDraft((old) => old.map((s) => (s.id === slot.id ? { ...s, text: e.target.value } : s)))}
                  onKeyDown={(e) => {
                    if (!e.altKey || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return
                    e.preventDefault()
                    stepFocus(slot.id, e.key === 'ArrowDown' ? 1 : -1)
                  }}
                />
                {suggestions.length > 0 && (
                  <div className="suggest-chips" aria-label={t('cal.suggestFor', { n: fa(index + 1) })}>
                    {suggestions.map((term) => (
                      <button
                        key={term.id}
                        type="button"
                        className="suggest-chip"
                        disabled={disabled}
                        title={term.source_term}
                        aria-label={t('cal.insertFor', { target: term.target_term, source: term.source_term })}
                        onClick={() => insertSuggestion(slot.id, term.target_term)}
                      >
                        {term.target_term}
                      </button>
                    ))}
                  </div>
                )}
                {showDiff && changed && (
                  <div className="slot-diff" aria-hidden="true" dir="auto">
                    {parts.map((part, i) =>
                      part.kind === 'same' ? (
                        <span key={i}>{part.text}</span>
                      ) : (
                        <mark key={i} className={part.kind === 'add' ? 'diff-add' : 'diff-del'}>
                          {part.kind === 'add' ? '+' : '−'}
                          {part.text}
                        </mark>
                      ),
                    )}
                  </div>
                )}
                {showDiff && changed && (
                  <p className="sr-only">
                    {t('cal.diffSummary', { n: fa(index + 1), added: fa(added), removed: fa(removed) })}
                  </p>
                )}
                <div className="slot-actions">
                  {changed ? (
                    <span className="badge badge-info">{t('cal.editedBadge')}</span>
                  ) : (
                    <span className="badge">{t('cal.sameBadge')}</span>
                  )}
                  {changed && (
                    <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => revertSlot(slot.id)}>
                      {t('cal.revertSlot')}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
      {dirty && (
        <div className="calibration-actions">
          <span className="calibration-muted">{t('cal.dirtyNote')}</span>
          <button type="button" className="btn btn-primary" disabled={disabled || draft.some((s) => !s.text.trim())} onClick={() => onSave(draft)}>
            {t('cal.saveEdit')}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setDraft(sample.result?.translations ?? [])}>
            {t('cal.discardEdit')}
          </button>
        </div>
      )}
    </>
  )
}

export function GlossaryEditor({ terms, disabled, onSave, onPropose }: { terms: CalibrationTerm[]; disabled: boolean; onSave: (terms: CalibrationTerm[], unlock: string[]) => void; onPropose: () => void }) {
  const { t } = useLanguage()
  const [draft, setDraft] = useState(terms)
  const [unlocked, setUnlocked] = useState<string[]>([])
  const change = (id: string, patch: Partial<CalibrationTerm>) => setDraft(old => old.map(s => s.id === id ? { ...s, ...patch } : s))
  const dirty = JSON.stringify(draft) !== JSON.stringify(terms)
  return <section className="surface-card calibration-section"><div className="calibration-section-title"><div><h2>{t('cal.glossTitle')}</h2><p className="calibration-muted">{t('cal.glossHint')}</p></div><button type="button" className="btn btn-secondary" disabled={disabled || dirty} onClick={onPropose}>{t('cal.suggestTerms')}</button></div>
    {draft.length === 0 && <p className="calibration-empty">{t('cal.glossEmpty')}</p>}
    <div className="calibration-terms">{draft.map((term, index) => <div className="calibration-term" key={term.id}>
      <label>{t('cal.srcTerm')}<input className="field" dir="auto" aria-label={t('cal.termN', { n: fa(index + 1) })} value={term.source_term} disabled={disabled || term.locked} onChange={e => change(term.id, { source_term: e.target.value })} /></label>
      <label>{t('cal.trTerm')}<input className="field" aria-label={t('cal.trN', { n: fa(index + 1) })} value={term.target_term} disabled={disabled || term.locked} onChange={e => change(term.id, { target_term: e.target.value })} /></label>
      <div className="term-controls"><label><input type="checkbox" checked={term.approved} disabled={disabled || term.locked} onChange={e => change(term.id, { approved: e.target.checked })} />{t('cal.approve')}</label><button type="button" className="btn btn-ghost" disabled={disabled || (!term.approved && !term.locked)} onClick={() => { if (term.locked) setUnlocked(old => [...old, term.id]); change(term.id, { locked: !term.locked }) }}>{term.locked ? t('cal.unlock') : t('cal.lock')}</button><button type="button" className="btn btn-ghost" disabled={disabled || term.locked} aria-label={t('cal.deleteTerm', { name: term.source_term || t('cal.delete') })} onClick={() => setDraft(old => old.filter(x => x.id !== term.id))}>{t('cal.delete')}</button></div>
      <label className="term-notes">{t('cal.termNotes')}<input className="field" value={term.notes} disabled={disabled || term.locked} maxLength={1000} onChange={e => change(term.id, { notes: e.target.value })} /></label>
    </div>)}</div>
    <div className="calibration-actions"><button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => setDraft(old => [...old, { id: crypto.randomUUID(), source_term: '', target_term: '', notes: '', approved: true, locked: false, kind: 'term', evidence_id: '' }])}>{t('cal.newTerm')}</button><button type="button" className="btn btn-primary" disabled={disabled || !dirty} onClick={() => onSave(draft, unlocked)}>{t('cal.saveGloss')}</button>{dirty && <span className="calibration-muted">{t('cal.dirtyGloss')}</span>}</div>
  </section>
}

export function CostPanel({ session: s }: { session: Calibration }) {
  const { t } = useLanguage()
  const q = s.quote
  return <section className="surface-card calibration-section cost-panel"><h2>{t('cal.costTitle')}</h2><dl>
    <div><dt>{t('cal.spent')}</dt><dd>{formatCost(q.spent_cost)}</dd></div>
    <div><dt>{t('cal.reserved')}</dt><dd>{formatCost(q.reserved_cost)}</dd></div>
    <div><dt>{t('cal.sampleLeft')}</dt><dd>{formatCost(q.sample_cost)}</dd></div>
    <div className="cost-total"><dt>{t('cal.remaining')}</dt><dd>{formatCost(q.remaining_cost_low)} {t('cal.costTo')} {formatCost(q.remaining_cost_high)}</dd></div>
    <div><dt>{t('cal.tokensUsed')}</dt><dd>{fa(q.spent_tokens)} / {fa(q.reserved_tokens)}</dd></div>
    <div><dt>{t('cal.sampleCalls')}</dt><dd>{fa(q.sample_calls)} {t('cal.ofTotal', { total: fa(s.budget.max_calls) })}</dd></div>
    <div><dt>{t('cal.reusable')}</dt><dd>{fa(q.reusable_units)}</dd></div>
  </dl><p className="calibration-muted">{q.pricing === 'configured' ? t('cal.pricingConfigured') : q.pricing === 'estimated' ? t('cal.pricingEstimated') : t('cal.pricingUnknown')} {t('cal.pricingTail')}</p></section>
}

export function BudgetEditor({ value, disabled, configured, onSave }: { value: CalibrationBudget; disabled: boolean; configured: boolean; onSave: (budget: CalibrationBudget) => void }) {
  const { t } = useLanguage()
  const [draft, setDraft] = useState(value)
  return <details className="surface-card calibration-section"><summary>{t('cal.budgetTitle')}</summary><div className="budget-fields">
    <label>{t('cal.budgetSample')}<input className="field" type="number" min={1000} max={5000000} step={1000} disabled={disabled} value={draft.sample_tokens} onChange={e => setDraft({ ...draft, sample_tokens: Number(e.target.value) })} /></label>
    <label>{t('cal.budgetTotal')}<input className="field" type="number" min={1000} max={100000000} step={1000} disabled={disabled} value={draft.total_tokens} onChange={e => setDraft({ ...draft, total_tokens: Number(e.target.value) })} /></label>
    <label>{t('cal.budgetCalls')}<input className="field" type="number" min={1} max={100} disabled={disabled} value={draft.max_calls} onChange={e => setDraft({ ...draft, max_calls: Number(e.target.value) })} /></label>
    {configured && <label>{t('cal.budgetUsd')}<input className="field" type="number" min={0.01} step={0.01} disabled={disabled} value={draft.max_cost_micros === null ? '' : draft.max_cost_micros / 1e6} onChange={e => setDraft({ ...draft, max_cost_micros: e.target.value ? Math.round(Number(e.target.value) * 1e6) : null })} /></label>}
    <button className="btn btn-secondary" type="button" disabled={disabled || JSON.stringify(draft) === JSON.stringify(value)} onClick={() => onSave(draft)}>{t('cal.budgetSave')}</button>
  </div></details>
}
