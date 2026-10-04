import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { fa } from '@/lib/format'
import { calibrationApi, canSeal, formatCost, replaceSample } from '@/lib/calibration'
import type { Calibration, CalibrationBudget, CalibrationOperation, CalibrationPatch, CalibrationSample, CalibrationTerm, TextSlot } from '@/lib/calibration'
import '@/styles/calibration.css'

const roleLabel: Record<string, string> = { narrative: 'روایت و توضیح', technical: 'متن تخصصی', dialogue: 'گفت‌وگو' }

export function CalibrationPage() {
  const { id = '' } = useParams()
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

  if (query.isPending) return <main className="page" dir="rtl"><h1>آماده‌سازی کارگاه ترجمه…</h1><div className="skeleton mt-5" style={{ height: 250 }} /></main>
  if (!session || query.isError) return <main className="page" dir="rtl"><p role="alert" className="alert alert-error">{query.error?.message ?? 'جلسه پیدا نشد.'}</p><Link className="btn btn-secondary mt-4" to="/workspace">بازگشت به افزودن کتاب</Link></main>

  const current = session.samples.find(s => s.id === activeId) ?? session.samples[0]
  const inProgress = !!session.busy || generate.isPending || ['running', 'queued'].includes(operation.data?.status ?? '')
  const disabled = inProgress || action.isPending || start.isPending || !!session.job_id
  const patch = (value: CalibrationPatch) => { setError(null); action.mutate(() => calibrationApi.edit(session, value)) }
  const run = (ids: string[], final = true) => { setError(null); generate.mutate(() => calibrationApi.generate(session, ids, final)) }

  return <main className="page calibration-page" dir="rtl">
    <header className="calibration-header">
      <div><Link to="/workspace" className="calibration-back">← افزودن کتاب</Link><h1>اول نمونه، بعد کتاب</h1><p className="calibration-muted">{session.filename} · {fa(session.unit_count)} بخش قابل پردازش</p></div>
      <span className="calibration-pill">{session.job_id ? 'پروفایل قفل‌شده' : session.approved_profile_hash ? 'آمادهٔ شروع' : 'کارگاه تنظیم ترجمه'}</span>
    </header>
    <ol className="calibration-steps" aria-label="مراحل ترجمه">
      {['انتخاب نمونه', 'لحن و واژه‌نامه', 'بررسی و تأیید', 'ترجمهٔ کتاب'].map((label, i) => <li key={label} aria-current={i === (session.job_id ? 3 : session.approved_profile_hash ? 2 : 1) ? 'step' : undefined}><span>{fa(i + 1)}</span>{label}</li>)}
    </ol>
    {session.warnings.length > 0 && <details className="alert alert-warning"><summary>نکات استخراج متن ({fa(session.warnings.length)})</summary>{session.warnings.map((w, i) => <p key={i}>{w}</p>)}</details>}
    {(error || operation.data?.error) && <p role="alert" className="alert alert-error">{error ?? operation.data?.error}</p>}
    {inProgress && <div role="status" className="alert alert-info calibration-progress"><span>در حال آماده‌کردن نتیجه… {operation.data?.total ? `${fa(operation.data.completed)} از ${fa(operation.data.total)}` : ''}</span><button type="button" className="btn btn-ghost" disabled={!session.busy} onClick={() => { if (session.busy) void calibrationApi.cancel(session.busy).catch(fail) }}>توقف پس از درخواست جاری</button></div>}

    <div className="calibration-layout">
      <div className="calibration-main">
        <section className="surface-card calibration-section" aria-labelledby="tone-heading">
          <div className="calibration-section-title"><div><h2 id="tone-heading">صدای ترجمه را انتخاب کنید</h2><p className="calibration-muted">تغییر لحن، نمونهٔ باز را با مدل نهایی بازتولید می‌کند؛ باقی نمونه‌ها پیش از تأیید تازه می‌شوند.</p></div></div>
          <div className="tone-matrix" role="group" aria-label="لحن ترجمه">{session.tones.map(tone => <button type="button" key={tone.id} disabled={disabled} className="tone-choice" aria-pressed={session.profile.tone === tone.id} onClick={() => {
            if (tone.id === session.profile.tone) return
            setError(null)
            generate.mutate(async () => {
              const next = await calibrationApi.edit(session, { tone: tone.id }); update(next)
              return calibrationApi.generate(next, current ? [current.id] : next.samples.map(s => s.id))
            })
          }}><strong>{tone.label}</strong><span>{tone.description}</span></button>)}</div>
          <div className="calibration-models">
            <label>مدل پیشنویس<select className="field" value={session.profile.model} disabled={disabled} onChange={e => patch({ model: e.target.value })}>{(models.data?.items ?? []).map(m => <option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
            <label>مدل ترجمهٔ نهایی<select className="field" value={session.profile.final_model} disabled={disabled} onChange={e => patch({ final_model: e.target.value })}>{(models.data?.items ?? []).map(m => <option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
          </div>
          {session.profile.model !== session.profile.final_model && <p className="calibration-muted">پیشنویس برای مقایسه است. پیش از شروع، نمونه‌ها باید با مدل نهایی تولید و تأیید شوند.</p>}
          <Instructions key={`instructions-${session.revision}`} value={session.profile.instructions} disabled={disabled} onSave={value => patch({ instructions: value })} />
        </section>

        <section className="surface-card calibration-section" aria-labelledby="samples-heading">
          <div className="calibration-section-title"><div><h2 id="samples-heading">متن اصلی و ترجمه</h2><p className="calibration-muted">نمونه‌ها از بخش‌های متفاوت کتاب انتخاب شده‌اند. برای تغییر، فصل و بخش دیگری انتخاب کنید.</p></div><label className="calibration-check"><input type="checkbox" checked={sync} onChange={e => setSync(e.target.checked)} />حرکت هم‌زمان</label></div>
          <div className="sample-tabs" role="tablist" aria-label="نمونه‌ها">{session.samples.map((sample, i) => <button type="button" role="tab" aria-selected={sample.id === current?.id} key={sample.id} onClick={() => setActiveId(sample.id)}><span>نمونهٔ {fa(i + 1)}</span><small>{roleLabel[sample.role] ?? sample.role}</small><span aria-label={sample.approved ? 'تأییدشده' : 'نیازمند بررسی'}>{sample.approved ? '✓' : '○'}</span></button>)}</div>
          {current && <>
            <label className="calibration-replace">جایگزینی نمونه<select className="field" disabled={disabled} value={current.id} onChange={e => { const next = e.target.value; patch({ selected: replaceSample(session, current.id, next) }); setActiveId(next) }}>{session.candidates.filter(c => c.id === current.id || !session.samples.some(s => s.id === c.id)).map(c => <option key={c.id} value={c.id}>{c.chapter} — {c.excerpt.slice(0, 75)}</option>)}</select></label>
            {current.result?.reused && <p role="status" className="calibration-muted">این نتیجه از حافظه بازیابی شده؛ درخواست تازه‌ای برای آن ارسال نشد.</p>}
            {current.result && !current.final_verified && <p className="alert alert-warning">این پیشنویس با مدل نهایی تأیید نشده است.</p>}
            <ParallelEditor key={`${current.id}-${session.revision}`} sample={current} sync={sync} disabled={disabled || !current.final_verified} sourceLang={session.profile.from_lang} onSave={translations => action.mutate(() => calibrationApi.feedback(session, current.id, translations))} />
            <div className="calibration-actions">
              <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => run([current.id])}>{current.result ? 'تولید با تنظیمات فعلی' : 'ترجمهٔ این نمونه'}</button>
              {session.profile.model !== session.profile.final_model && <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => run([current.id], false)}>پیشنویس با مدل اقتصادی</button>}
              <button type="button" className="btn btn-primary" disabled={disabled || !current.final_verified || current.approved} onClick={() => action.mutate(() => calibrationApi.approveSample(session, current.id))}>{current.approved ? '✓ نمونه تأیید شده' : 'این نمونه را تأیید می‌کنم'}</button>
            </div>
          </>}
          <button type="button" className="btn btn-ghost mt-3" disabled={disabled} onClick={() => run(session.samples.filter(s => !s.final_verified).map(s => s.id))}>تولید همهٔ نمونه‌های نیازمند بررسی</button>
        </section>

        <GlossaryEditor key={`glossary-${session.revision}`} terms={session.profile.glossary} disabled={disabled}
          onSave={(terms, unlockIds) => patch({ glossary: terms, unlock_ids: unlockIds })}
          onPropose={() => { setError(null); generate.mutate(() => calibrationApi.propose(session)) }} />
      </div>

      <aside className="calibration-sidebar">
        <CostPanel session={session} />
        <BudgetEditor key={`budget-${session.revision}`} value={session.budget} disabled={disabled} configured={session.quote.pricing === 'configured'} onSave={budget => patch({ budget })} />
        <section className="surface-card calibration-section calibration-approval">
          <h2>آمادهٔ ترجمهٔ کامل؟</h2><p>{fa(session.samples.filter(s => s.approved).length)} از {fa(session.samples.length)} نمونه تأیید شده</p>
          <p className="calibration-muted">واژه‌نامه و لحن در شروع قفل می‌شوند. بخش‌های تأییدشده با همان تنظیمات دوباره هزینه نمی‌شوند.</p>
          <p className="calibration-muted">تأیید چند نمونه تضمین کیفیت همهٔ کتاب نیست؛ خروجی نهایی را بازبینی کنید.</p>
          {session.job_id ? <Link className="btn btn-primary" to={`/jobs/${session.job_id}`}>مشاهدهٔ ترجمه</Link> : session.approved_profile_hash ? <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => start.mutate()}>شروع ترجمه با این برآورد</button> : <button type="button" className="btn btn-primary" disabled={disabled || !canSeal(session)} onClick={() => action.mutate(() => calibrationApi.approve(session))}>قفل پروفایل و تأیید نهایی</button>}
        </section>
      </aside>
    </div>
  </main>
}

function Instructions({ value, disabled, onSave }: { value: string; disabled: boolean; onSave: (value: string) => void }) {
  const [draft, setDraft] = useState(value)
  return <details className="calibration-instructions"><summary>راهنمای تکمیلی برای تمام کتاب</summary><label>ترجیحات لحن و نگارش<textarea className="field" rows={3} maxLength={2000} value={draft} disabled={disabled} placeholder="مثلاً: لحن گفت‌وگوها طبیعی باشد؛ روایت رسمی بماند." onChange={e => setDraft(e.target.value)} /></label><button className="btn btn-secondary" type="button" disabled={disabled || draft === value} onClick={() => onSave(draft)}>ثبت راهنمای کتاب</button><p className="calibration-muted">ویرایش یک جمله فقط همان بخش را تغییر می‌دهد. ترجیح کلی را اینجا ثبت کنید.</p></details>
}

function ParallelEditor({ sample, sync, disabled, sourceLang, onSave }: { sample: CalibrationSample; sync: boolean; disabled: boolean; sourceLang: string; onSave: (slots: TextSlot[]) => void }) {
  const [draft, setDraft] = useState(sample.result?.translations ?? [])
  const source = useRef<HTMLDivElement>(null)
  const target = useRef<HTMLDivElement>(null)
  const moving = useRef(false)
  const dirty = JSON.stringify(draft) !== JSON.stringify(sample.result?.translations ?? [])
  function align(from: HTMLDivElement, to: HTMLDivElement | null) {
    if (!sync || !to || moving.current) return
    const blocks = [...from.querySelectorAll<HTMLElement>('[data-slot]')]
    const top = from.getBoundingClientRect().top
    const anchor = blocks.find(b => b.getBoundingClientRect().bottom > top + 4)
    if (!anchor) return
    const matching = [...to.querySelectorAll<HTMLElement>('[data-slot]')].find(b => b.dataset.slot === anchor.dataset.slot)
    if (!matching) return
    moving.current = true
    const fraction = (top - anchor.getBoundingClientRect().top) / Math.max(1, anchor.offsetHeight)
    to.scrollTop += matching.getBoundingClientRect().top - to.getBoundingClientRect().top + fraction * matching.offsetHeight
    requestAnimationFrame(() => { moving.current = false })
  }
  return <><div className="parallel-labels"><strong>متن اصلی</strong><strong>ترجمهٔ فارسی {sample.result?.origin === 'human_edit' ? '· ویرایش شما' : ''}</strong></div>
    <div className="parallel-editor" dir="ltr">
      <div ref={source} className="parallel-pane" lang={sourceLang.toLowerCase()} dir={['FA', 'AR', 'HE'].includes(sourceLang) ? 'rtl' : 'ltr'} onScroll={e => align(e.currentTarget, target.current)}>{sample.slots.map(slot => <p data-slot={slot.id} key={slot.id}>{slot.text}</p>)}</div>
      <div ref={target} className="parallel-pane" dir="rtl" lang="fa" onScroll={e => align(e.currentTarget, source.current)}>{!sample.result ? <div className="calibration-empty"><strong>هنوز ترجمه‌ای تولید نشده</strong><p>با «ترجمهٔ این نمونه» نتیجه را ببینید؛ سپس لحن و اصطلاحات را تنظیم کنید.</p></div> : draft.map((slot, index) => <div data-slot={slot.id} key={slot.id}><textarea aria-label={`ویرایش بند ${index + 1}`} className="sample-text" rows={Math.max(2, Math.min(12, Math.ceil(slot.text.length / 60)))} disabled={disabled} value={slot.text} onChange={e => setDraft(old => old.map(t => t.id === slot.id ? { ...t, text: e.target.value } : t))} /></div>)}</div>
    </div>{dirty && <div className="calibration-actions"><span className="calibration-muted">ویرایش محلی ذخیره نشده؛ پیش از تأیید ذخیره کنید.</span><button type="button" className="btn btn-primary" disabled={disabled || draft.some(t => !t.text.trim())} onClick={() => onSave(draft)}>ذخیرهٔ ویرایش این نمونه</button><button type="button" className="btn btn-ghost" onClick={() => setDraft(sample.result?.translations ?? [])}>بازگردانی</button></div>}</>
}

function GlossaryEditor({ terms, disabled, onSave, onPropose }: { terms: CalibrationTerm[]; disabled: boolean; onSave: (terms: CalibrationTerm[], unlock: string[]) => void; onPropose: () => void }) {
  const [draft, setDraft] = useState(terms)
  const [unlocked, setUnlocked] = useState<string[]>([])
  const change = (id: string, patch: Partial<CalibrationTerm>) => setDraft(old => old.map(t => t.id === id ? { ...t, ...patch } : t))
  const dirty = JSON.stringify(draft) !== JSON.stringify(terms)
  return <section className="surface-card calibration-section"><div className="calibration-section-title"><div><h2>واژه‌نامهٔ کتاب</h2><p className="calibration-muted">پیشنهادها از سراسر کتاب استخراج می‌شوند؛ فقط موارد تأییدشده وارد ترجمه می‌شوند.</p></div><button type="button" className="btn btn-secondary" disabled={disabled || dirty} onClick={onPropose}>پیشنهاد اصطلاحات</button></div>
    {draft.length === 0 && <p className="calibration-empty">واژه‌نامه هنوز خالی است. اصطلاح اضافه کنید یا پیشنهادها را بگیرید.</p>}
    <div className="calibration-terms">{draft.map((t, index) => <div className="calibration-term" key={t.id}>
      <label>عبارت اصلی<input className="field" dir="auto" aria-label={`عبارت ${index + 1}`} value={t.source_term} disabled={disabled || t.locked} onChange={e => change(t.id, { source_term: e.target.value })} /></label>
      <label>معادل فارسی<input className="field" aria-label={`معادل ${index + 1}`} value={t.target_term} disabled={disabled || t.locked} onChange={e => change(t.id, { target_term: e.target.value })} /></label>
      <div className="term-controls"><label><input type="checkbox" checked={t.approved} disabled={disabled || t.locked} onChange={e => change(t.id, { approved: e.target.checked })} />تأیید</label><button type="button" className="btn btn-ghost" disabled={disabled || (!t.approved && !t.locked)} onClick={() => { if (t.locked) setUnlocked(old => [...old, t.id]); change(t.id, { locked: !t.locked }) }}>{t.locked ? 'بازکردن قفل' : 'قفل'}</button><button type="button" className="btn btn-ghost" disabled={disabled || t.locked} aria-label={`حذف ${t.source_term || 'اصطلاح'}`} onClick={() => setDraft(old => old.filter(x => x.id !== t.id))}>حذف</button></div>
      <label className="term-notes">کاربرد و توضیح<input className="field" value={t.notes} disabled={disabled || t.locked} maxLength={1000} onChange={e => change(t.id, { notes: e.target.value })} /></label>
    </div>)}</div>
    <div className="calibration-actions"><button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => setDraft(old => [...old, { id: crypto.randomUUID(), source_term: '', target_term: '', notes: '', approved: true, locked: false, kind: 'term', evidence_id: '' }])}>+ اصطلاح تازه</button><button type="button" className="btn btn-primary" disabled={disabled || !dirty} onClick={() => onSave(draft, unlocked)}>ذخیرهٔ واژه‌نامه</button>{dirty && <span className="calibration-muted">تغییرات ذخیره نشده</span>}</div>
  </section>
}

function CostPanel({ session: s }: { session: Calibration }) {
  const q = s.quote
  return <section className="surface-card calibration-section cost-panel"><h2>هزینه زیر نظر شما</h2><dl>
    <div><dt>مصرف‌شده</dt><dd>{formatCost(q.spent_cost)}</dd></div>
    <div><dt>رزرو درخواست‌های جاری</dt><dd>{formatCost(q.reserved_cost)}</dd></div>
    <div><dt>نمونه‌های باقی‌مانده</dt><dd>{formatCost(q.sample_cost)}</dd></div>
    <div className="cost-total"><dt>برآورد ادامهٔ کل کتاب</dt><dd>{formatCost(q.remaining_cost_low)} تا {formatCost(q.remaining_cost_high)}</dd></div>
    <div><dt>توکن مصرف‌شده / رزرو</dt><dd>{fa(q.spent_tokens)} / {fa(q.reserved_tokens)}</dd></div>
    <div><dt>درخواست نمونه</dt><dd>{fa(q.sample_calls)} از {fa(s.budget.max_calls)}</dd></div>
    <div><dt>بخش قابل استفادهٔ مجدد</dt><dd>{fa(q.reusable_units)}</dd></div>
  </dl><p className="calibration-muted">{q.pricing === 'configured' ? 'نرخ از تنظیمات ارائه‌دهنده گرفته شده است.' : q.pricing === 'estimated' ? 'نرخ مدل تقریبی است؛ مبلغ فاکتور ارائه‌دهنده ممکن است متفاوت باشد. سقف توکن اعمال می‌شود.' : 'قیمت این مدل مشخص نیست. مبلغ صفر به معنی رایگان‌بودن نیست.'} شمارش توکن و هزینهٔ ادامه برآوردی است.</p></section>
}

function BudgetEditor({ value, disabled, configured, onSave }: { value: CalibrationBudget; disabled: boolean; configured: boolean; onSave: (budget: CalibrationBudget) => void }) {
  const [draft, setDraft] = useState(value)
  return <details className="surface-card calibration-section"><summary>سقف مصرف و تعداد تلاش‌ها</summary><div className="budget-fields">
    <label>سقف توکن نمونه‌ها<input className="field" type="number" min={1000} max={5000000} step={1000} disabled={disabled} value={draft.sample_tokens} onChange={e => setDraft({ ...draft, sample_tokens: Number(e.target.value) })} /></label>
    <label>سقف توکن کل کتاب<input className="field" type="number" min={1000} max={100000000} step={1000} disabled={disabled} value={draft.total_tokens} onChange={e => setDraft({ ...draft, total_tokens: Number(e.target.value) })} /></label>
    <label>حداکثر درخواست نمونه<input className="field" type="number" min={1} max={100} disabled={disabled} value={draft.max_calls} onChange={e => setDraft({ ...draft, max_calls: Number(e.target.value) })} /></label>
    {configured && <label>سقف دلار (اختیاری)<input className="field" type="number" min={0.01} step={0.01} disabled={disabled} value={draft.max_cost_micros === null ? '' : draft.max_cost_micros / 1e6} onChange={e => setDraft({ ...draft, max_cost_micros: e.target.value ? Math.round(Number(e.target.value) * 1e6) : null })} /></label>}
    <button className="btn btn-secondary" type="button" disabled={disabled || JSON.stringify(draft) === JSON.stringify(value)} onClick={() => onSave(draft)}>ثبت سقف جدید</button>
  </div></details>
}
