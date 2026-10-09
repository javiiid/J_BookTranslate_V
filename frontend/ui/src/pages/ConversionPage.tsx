import { useRef, useState } from 'react'
import { useConversion } from '@/hooks/useConversion'
import { CONVERSION_ACCEPT, CONVERSION_FORMATS, conversionFormatDescription, conversionFormatLabel } from '@/lib/conversion'
import { fa, faBytes } from '@/lib/format'
import { localeTag } from '@/lib/locale.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import './conversion.css'

export function ConversionPage() {
  const { t, lang, dir } = useLanguage()
  const { file, outputs, pending, error, entries, selectFiles, clearFile, toggleOutput, start } = useConversion()
  const listSeparator = lang === 'fa' ? '، ' : ', ';
  const [view, setView] = useState<'new' | 'history'>('new')
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const latest = entries[0]
  const visibleEntries = view === 'history' ? entries : entries.slice(0, 1)

  return (
    <main className="conversion-page page" dir={dir}>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="conversion-eyebrow">{t('convert.eyebrow')}</p>
          <h1 className="text-[length:var(--text-h1)] font-extrabold">{t('convert.title')}</h1>
          <p className="conversion-muted mt-2">{t('convert.subtitle')}</p>
        </div>
        <span className="badge badge-info">{t('convert.noAi')}</span>
      </header>

      <div className="conversion-switch mb-6" aria-label={t('convert.viewLabel')}>
        <button type="button" aria-pressed={view === 'new'} onClick={() => setView('new')}>{t('convert.tabNew')}</button>
        <button type="button" aria-pressed={view === 'history'} onClick={() => setView('history')}>
          {t('convert.tabHistory')} <span className="conversion-count">{fa(entries.length)}</span>
          {pending && <span className="conversion-muted"> · {t('convert.convertingNow')}</span>}
        </button>
      </div>

      {view === 'new' && (
        <form onSubmit={(event) => { event.preventDefault(); void start() }} className="conversion-layout">
          <div className="grid gap-5 min-w-0">
            <section className="surface-card p-5" aria-labelledby="conversion-upload-title">
              <h2 id="conversion-upload-title" className="conversion-section-title"><span className="conversion-step">{fa(1)}</span> {t('convert.step1')}</h2>
              <div
                className="conversion-drop mt-5"
                data-dragging={dragging && !pending}
                onDragOver={(event) => { event.preventDefault(); if (!pending) setDragging(true) }}
                onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false) }}
                onDrop={(event) => { event.preventDefault(); setDragging(false); selectFiles(Array.from(event.dataTransfer.files)) }}
              >
                <span className="conversion-file-icon" aria-hidden="true">⇄</span>
                <strong className="block mt-3">{t('convert.drop')}</strong>
                <p className="conversion-muted mt-1">{t('convert.dropHint')}</p>
                <button type="button" className="btn btn-secondary mt-4" disabled={pending} onClick={() => input.current?.click()}>
                  {file ? t('convert.chooseAnother') : t('convert.chooseOne')}
                </button>
                <input ref={input} type="file" className="sr-only" tabIndex={-1} aria-label={t('convert.fileAria')} accept={CONVERSION_ACCEPT} disabled={pending}
                  onChange={(event) => { selectFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
                <p className="conversion-muted mt-4"><bdi>EPUB · PDF · SRT · TXT · MD</bdi></p>
                <p className="conversion-muted mt-1">{t('convert.sizeLimit', { max: fa(1023) })}</p>
              </div>
              {file && (
                <div className="conversion-selected mt-4">
                  <span className="conversion-step" aria-hidden="true">✓</span>
                  <div className="min-w-0 flex-1"><strong className="block break-all"><bdi>{file.name}</bdi></strong><span className="conversion-muted">{faBytes(file.size)} · {t('convert.ready')}</span></div>
                  <button type="button" className="btn btn-ghost" disabled={pending} onClick={clearFile}>{t('convert.remove')}</button>
                </div>
              )}
            </section>

            <section className="surface-card p-5" aria-labelledby="conversion-output-title">
              <h2 id="conversion-output-title" className="conversion-section-title"><span className="conversion-step">{fa(2)}</span> {t('convert.step2')}</h2>
              <p className="conversion-muted mt-2">{t('convert.step2Hint')}</p>
              <fieldset disabled={pending} className="conversion-formats mt-5">
                <legend className="sr-only">{t('convert.formatsLegend')}</legend>
                {CONVERSION_FORMATS.map((format) => (
                  <label key={format.id} className="conversion-format" data-selected={outputs.includes(format.id)}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="conversion-extension">{format.extension}</span>
                      <input type="checkbox" checked={outputs.includes(format.id)} onChange={() => toggleOutput(format.id)} />
                    </div>
                    <strong className="block mt-3">{conversionFormatLabel(format.id)}</strong>
                    <span className="conversion-muted block mt-1">{conversionFormatDescription(format.id)}</span>
                  </label>
                ))}
              </fieldset>
              {outputs.includes('txt_bilingual') && <p className="alert alert-info mt-4">{t('convert.txtNote')}</p>}
            </section>
          </div>

          <aside className="conversion-summary surface-card p-5">
            <h2 className="conversion-section-title"><span className="conversion-step">{fa(3)}</span> {t('convert.step3')}</h2>
            <dl className="conversion-details mt-5">
              <div><dt>{t('convert.inFile')}</dt><dd className="break-all">{file ? <bdi>{file.name}</bdi> : t('convert.notChosen')}</dd></div>
              <div><dt>{t('convert.fileSize')}</dt><dd>{file ? faBytes(file.size) : '—'}</dd></div>
              <div><dt>{t('convert.outCount')}</dt><dd>{t('convert.formatCount', { count: fa(outputs.length) })}</dd></div>
            </dl>
            <div className="flex flex-wrap gap-2 mt-4">{outputs.map((output) => <span key={output} className="badge badge-info">{conversionFormatLabel(output)}</span>)}</div>
            <button type="submit" className="btn btn-primary w-full mt-6" disabled={pending || !file || !outputs.length}>
              {pending ? t('convert.sending') : t('convert.start')}
            </button>
            <p className="conversion-muted mt-3">{t('convert.serverNote')}</p>
            <div className="conversion-notes mt-5">
              <strong>{t('convert.beforeStart')}</strong>
              <ul className="list-disc ps-5 mt-2 space-y-2">
                <li>{t('convert.note1')}</li>
                <li>{t('convert.note2')}</li>
                <li>{t('convert.note3')}</li>
                <li>{t('convert.note4')}</li>
              </ul>
            </div>
          </aside>
        </form>
      )}

      {error && view === 'new' && <p role="alert" className="alert alert-error mt-5">{error}</p>}
      <section className="mt-6" aria-labelledby="conversion-results-title" aria-live="polite" aria-busy={pending}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 id="conversion-results-title" className="conversion-section-title">{view === 'history' ? t('convert.historyTitle') : t('convert.resultsTitle')}</h2>
          {view === 'new' && entries.length > 1 && <button type="button" className="btn btn-ghost" onClick={() => setView('history')}>{t('convert.viewAll')}</button>}
        </div>
        {view === 'history' && <p className="conversion-muted mb-4">{t('convert.historyNote')}</p>}
        {!visibleEntries.length ? (
          <div className="surface-card p-8 text-center"><span className="conversion-file-icon" aria-hidden="true">↓</span><p className="font-semibold mt-3">{view === 'history' ? t('convert.emptyHistory') : t('convert.emptyNew')}</p><p className="conversion-muted mt-2">{t('convert.emptyHint')}</p></div>
        ) : (
          <div className="grid gap-4">
            {visibleEntries.map((entry) => {
              const missing = entry.result ? entry.outputs.filter((output) => !entry.result?.versions.some((version) => version.name === output)) : []
              return (
                <article key={entry.key} className="surface-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0"><h3 className="font-semibold break-all"><bdi>{entry.filename}</bdi></h3><p className="conversion-muted mt-1">{new Date(entry.createdAt).toLocaleString(localeTag())} · {entry.outputs.map(conversionFormatLabel).join(listSeparator)}</p></div>
                    <span className={`badge ${entry.error ? 'badge-error' : !entry.result ? 'badge-info' : missing.length ? 'badge-warning' : 'badge-success'}`}>
                      {entry.error ? t('convert.statusFailed') : !entry.result ? t('convert.statusSending') : missing.length ? t('convert.statusPartial') : t('convert.statusReady')}
                    </span>
                  </div>
                  {!entry.result && !entry.error && <p className="alert alert-info mt-4">{t('convert.sendingNote')}</p>}
                  {entry.error && <p className="alert alert-error mt-4">{entry.error}</p>}
                  {missing.length > 0 && <p className="alert alert-warning mt-4">{t('convert.missingNote', { list: missing.map(conversionFormatLabel).join(listSeparator) })}</p>}
                  {entry.result && <div className="flex flex-wrap gap-3 mt-4">{entry.result.versions.map((version) => <a key={version.name} href={version.download} download={version.filename} className="btn btn-secondary">↓ {t('convert.download', { label: conversionFormatLabel(version.name) })}</a>)}</div>}
                  {entry === latest && entry.error && view === 'history' && <button type="button" className="btn btn-secondary mt-4" onClick={() => setView('new')}>{t('convert.backToSettings')}</button>}
                </article>
              )
            })}
          </div>
        )}
      </section>

      <details className="conversion-help surface-card p-5 mt-6">
        <summary className="font-semibold cursor-pointer">{t('convert.faqQ')}</summary>
        <div className="conversion-muted mt-4 space-y-3">
          <p>{t('convert.faq1')}</p>
          <p>{t('convert.faq2')}</p>
          <p>{t('convert.faq3')}</p>
          <p>{t('convert.faq4')}</p>
        </div>
      </details>
    </main>
  )
}
