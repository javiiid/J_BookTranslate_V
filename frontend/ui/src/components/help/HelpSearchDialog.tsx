/**
 * The help command dialog: `Ctrl+K` (or `⌘K` on macOS) from anywhere in
 * the product surface.
 *
 * There is no app-wide command palette to merge into (checked), so this
 * dialog stands alone rather than pretending to be global infrastructure.
 * It shares `searchHelp` with `/help`, so the page and the dialog can
 * never disagree about what exists.
 *
 * Keyboard contract: opens with the shortcut, focuses the field, moves
 * with Up/Down, opens with Enter, closes with Escape, and hands focus
 * back to whatever opened it. The listener is removed on unmount, and
 * IME composition never triggers an action.
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { searchHelp } from '@/lib/help.ts'
import type { HelpSearchResult } from '@/lib/help.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { useHelpCorpus, helpResultPath } from '@/help/corpus'
import { Highlight } from './helpUi'
import { fa } from '@/lib/format'

const RESULT_LIMIT = 8

export function HelpSearchDialog() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const { corpus } = useHelpCorpus()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const opener = useRef<HTMLElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const titleId = useId()
  const listId = useId()

  const results: HelpSearchResult[] = useMemo(
    () => searchHelp(query, corpus, { limit: RESULT_LIMIT }),
    [query, corpus],
  )

  useEffect(() => {
    setActive(0)
  }, [query, corpus])

  // The global shortcut. One listener, cleaned up on unmount; composing
  // text (IME) and already-handled events are left alone.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k') return
      if (event.shiftKey || event.altKey) return
      event.preventDefault()
      opener.current = (document.activeElement as HTMLElement | null) ?? null
      setOpen((was) => !was)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Focus the field on open, lock the page scroll, hand focus back on close.
  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus())
    return () => {
      window.cancelAnimationFrame(frame)
      document.body.style.overflow = previousOverflow
      opener.current?.focus?.()
      opener.current = null
    }
  }, [open])

  // Close when the route changes underneath (e.g. browser Back).
  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  if (!open) return null

  const close = () => setOpen(false)

  const go = (result: HelpSearchResult) => {
    setOpen(false)
    void navigate(helpResultPath(result))
  }

  const typeName = (kind: HelpSearchResult['kind']): string =>
    kind === 'article' ? t('help.typeArticle') : kind === 'faq' ? t('help.typeFaq') : t('help.typeVideo')

  const onFieldKey = (event: React.KeyboardEvent) => {
    if (event.nativeEvent.isComposing) return
    if (event.key === 'Escape') {
      event.preventDefault()
      close()
    } else if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault()
      setActive((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp' && results.length > 0) {
      event.preventDefault()
      setActive((index) => (index - 1 + results.length) % results.length)
    } else if (event.key === 'Enter' && results.length > 0) {
      event.preventDefault()
      const chosen = results[Math.min(active, results.length - 1)]
      if (chosen) go(chosen)
    }
  }

  return (
    <div className="modal-overlay" onMouseDown={close}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{ width: 'min(36rem, 100%)' }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id={titleId} className="text-[length:var(--text-h3)] font-extrabold">
          {t('help.dialogTitle')}
        </h2>
        <p className="mt-[var(--spacing-1)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
          {t('help.dialogHint')}
        </p>
        <input
          ref={inputRef}
          type="search"
          className="field mt-[var(--spacing-3)] w-full"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onFieldKey}
          placeholder={t('help.searchPh')}
          aria-label={t('help.searchLabel')}
          aria-expanded={results.length > 0}
          aria-controls={listId}
          role="combobox"
          aria-autocomplete="list"
        />
        <div aria-live="polite" className="mt-[var(--spacing-2)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
          {query.trim()
            ? results.length > 0
              ? t('help.resultsFor', { n: fa(results.length), q: query.trim() })
              : t('help.dialogNone')
            : t('help.dialogEmpty')}
        </div>
        {results.length > 0 ? (
          <ul id={listId} role="listbox" aria-label={t('help.searchLabel')} className="help-result-list">
            {results.map((result, index) => (
              <li key={`${result.kind}:${result.ref}`} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={index === active}
                  data-active={index === active}
                  className="help-result"
                  onClick={() => go(result)}
                  onMouseMove={() => setActive(index)}
                >
                  <span className="badge flex-none">{typeName(result.kind)}</span>
                  <span className="min-w-0">
                    <span className="help-result-title">
                      <Highlight text={result.title} query={query} />
                    </span>
                    <span className="help-result-summary">{result.summary.slice(0, 140)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
