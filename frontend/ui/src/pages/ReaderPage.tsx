import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Chapter, ChapterBlock, ChapterContent, ReadingSettings } from '@/lib/api'
import { stripDuplicatedHeading, stripLeadingTitle } from '@/lib/chunks'
import {
  MAX_GLOSS_MARKS,
  findTermAt,
  prepareGlossTerms,
  textFor,
  tipFor,
  type GlossSide,
  type GlossTerm,
} from '@/lib/glossary.ts'
import {
  DIRECTION_OPTIONS,
  LINE_HEIGHT_FALLBACK,
  LINE_HEIGHT_OPTIONS,
  READER_MODES,
  WIDTH_FALLBACK,
  WIDTH_OPTIONS,
  clampFontSize,
  clampLineHeight,
  clampWidth,
  directionFor,
  isDirection,
  locationKey,
  overallPercent,
  readKey,
  storedChapter,
  toReaderMode,
  type ReaderMode,
} from '@/lib/reading.ts'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { StringKey } from '@/i18n/fa.ts'
import './reader.css'

/**
 * The bilingual reader.
 *
 * Ported from `app/reader/page.py`.
 *
 * ONE RULE DOMINATES THIS FILE: the HTML rendered here is sanitised by the
 * Python `sanitize_html` boundary before it ever reaches this client. Do not
 * add client-side sanitisation, and do not widen what is rendered. The
 * protection is the boundary, and the tests in
 * `D:\J_BookTranslate_V\tests\test_reader_images.py` cover it. Re-implementing
 * it here in TypeScript would create a second, differently-flawed copy of the
 * one thing that keeps a hostile EPUB from running script in this origin.
 *
 * Images arrive as local asset URLs (`/reader/<id>/asset/<path>`) which the
 * backend serves with a sandboxing CSP. That is why the block HTML can be
 * injected whole: there is no remote origin in it.
 */

const MODE_KEY: Record<ReaderMode, StringKey> = {
  translation: 'reader.mode.translation',
  original: 'reader.mode.original',
  bilingual: 'reader.mode.bilingual',
  columns: 'reader.mode.columns',
}

const DIRECTION_KEY: Record<string, StringKey> = {
  auto: 'reader.direction.auto',
  rtl: 'reader.direction.rtl',
  ltr: 'reader.direction.ltr',
}

/**
 * Local-storage helpers. Reads are total (missing/corrupt → empty), writes
 * never throw (private mode) — a preference that cannot persist must not
 * break the reader.
 */
function readJson(key: string): unknown {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as unknown) : null
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private browsing: the preference lives in memory for this visit.
  }
}

function loadReadIds(jobId: string): number[] {
  const raw = readJson(readKey(jobId))
  if (!Array.isArray(raw)) return []
  return raw.filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
}

/** Saved scroll fraction for a chapter, or null when nothing was kept. */
function loadSavedFrac(jobId: string, chapter: number): number | null {
  const raw = readJson(locationKey(jobId))
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as { chapter?: unknown; frac?: unknown }
  if (record.chapter !== chapter) return null
  if (typeof record.frac !== 'number' || !Number.isFinite(record.frac)) return null
  return Math.min(1, Math.max(0, record.frac))
}
/**
 * DOM helpers for glossary highlighting. They touch `document` and are
 * therefore exercised by hand, not by `node --test` — everything decidable
 * without a DOM lives tested in `lib/glossary.ts`.
 *
 * Mirrors `applyGloss`/`clearGloss` in `app/reader/page.py`: longest-first
 * terms, one mark per (node, term), 200 marks per chapter, marks cleared
 * before every re-apply so toggling mode or chapter never double-wraps.
 */

/** Which language a text node is in, from the nearest marked ancestor. */
function sideOfNode(node: Text, mode: ReaderMode): GlossSide | null {
  const element = node.parentElement
  if (!element) return null
  const marked = element.closest('[data-gloss-side]')
  const side = marked?.getAttribute('data-gloss-side')
  if (side === 'source' || side === 'target') return side
  return mode === 'original' ? 'source' : 'target'
}

/** Unwrap every highlight mark, restoring the original text nodes. */
function clearGlossMarks(root: Element): void {
  for (const mark of Array.from(root.querySelectorAll('mark.gloss'))) {
    mark.replaceWith(...Array.from(mark.childNodes))
  }
  root.normalize()
}

/** Collect highlightable text nodes before mutating, so the walk sees a stable list. */
function glossTextNodes(root: Element): Text[] {
  const nodes: Text[] = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node: Node): number {
      if (!node.nodeValue?.trim()) return NodeFilter.FILTER_REJECT
      const element = (node as Text).parentElement
      if (!element || element.closest('mark.gloss, script, style')) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let current = walker.nextNode()
  while (current) {
    nodes.push(current as Text)
    current = walker.nextNode()
  }
  return nodes
}

function applyGlossMarks(
  root: Element,
  terms: readonly GlossTerm[],
  mode: ReaderMode,
  label: string,
): number {
  let count = 0
  for (const textNode of glossTextNodes(root)) {
    let node: Text | null = textNode
    for (const term of terms) {
      if (!node || count >= MAX_GLOSS_MARKS) return count
      const side = sideOfNode(node, mode)
      if (!side) continue
      const match = findTermAt(node.nodeValue ?? '', textFor(term, side))
      if (!match) continue
      const middle = node.splitText(match.index)
      const after = middle.splitText(match.length)
      const mark = document.createElement('mark')
      mark.className = 'gloss'
      mark.tabIndex = 0
      mark.dataset.tip = tipFor(term, side)
      mark.setAttribute('aria-label', label)
      mark.appendChild(middle)
      node.parentNode?.insertBefore(mark, after)
      node = after
      count++
    }
  }
  return count
}

export function ReaderPage() {
  const { id = '' } = useParams()
  const { t, dir } = useLanguage()
  const client = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  // Local overrides until the next server round-trip. `null` means "follow
  // the server": the settings query is the source of truth, so a change made
  // in the Python reader (or another tab) is picked up instead of being
  // overwritten by this page's hardcoded defaults.
  const [modeOverride, setModeOverride] = useState<ReaderMode | null>(null)
  const [fontOverride, setFontOverride] = useState<number | null>(null)
  const [leadingOverride, setLeadingOverride] = useState<number | null>(null)
  const [widthOverride, setWidthOverride] = useState<number | null>(null)
  const [directionOverride, setDirectionOverride] = useState<string | null>(null)
  const [glossOverride, setGlossOverride] = useState<boolean | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const settings = useQuery({
    queryKey: ['reader-settings'],
    queryFn: () => api.readerSettings(),
    staleTime: 300_000,
  })

  const server = settings.data?.value
  const mode = modeOverride ?? toReaderMode(server?.reading_mode)
  const fontSize = fontOverride ?? server?.reading_font_size ?? 18
  const lineHeight = leadingOverride ?? server?.reading_line_height ?? LINE_HEIGHT_FALLBACK
  const width = widthOverride ?? server?.reading_width ?? WIDTH_FALLBACK
  const direction = directionOverride ?? server?.reading_direction ?? 'auto'
  // The toggle is persisted from this step on; highlighting itself lands
  // with the glossary step, which reads this same value.
  const glossary = glossOverride ?? server?.reading_glossary ?? true

  const chapters = useQuery({
    queryKey: ['reader-chapters', id],
    queryFn: () => api.readerChapters(id),
    enabled: Boolean(id),
  })

  // Read chapters per book (not per chapter): opening a new chapter marks
  // it read here and in localStorage, so the ticks survive a reload.
  const [readByBook, setReadByBook] = useState<Record<string, number[]>>({})
  const readIds = readByBook[id] ?? loadReadIds(id)
  // Scroll fraction per book+chapter: keyed, so switching books never shows
  // the other book's progress and no reset effect is needed.
  const [fracByKey, setFracByKey] = useState<Record<string, number>>({})
  const fracTimer = useRef<number>(0)

  // Derived, not stored in state via an effect. An effect that sets the chapter
  // on first load costs an extra render, and if it re-runs on a refetch it
  // silently yanks the reader back to chapter one. An explicit choice wins,
  // then the locally remembered chapter, then the server memory, then the
  // first chapter — all derived, so nothing can go stale.
  const chapterItems = chapters.data?.items ?? []
  const firstChapterId = chapterItems[0]?.id ?? null
  const validIds = chapterItems.map((chapter) => chapter.id)
  const localLoc = useMemo(() => readJson(locationKey(id)), [id])
  const chapterId = storedChapter(validIds, selectedId, localLoc, server?.reading_last_location)
    ?? firstChapterId
  const fracKey = `${id}:${chapterId ?? 'none'}`
  const frac = fracByKey[fracKey] ?? 0
  const chapterIndex = chapterId === null
    ? 0
    : Math.max(0, chapterItems.findIndex((chapter) => chapter.id === chapterId))
  const percent = overallPercent(chapterIndex, frac, chapterItems.length)

  const content = useQuery({
    queryKey: ['reader-chapter', id, chapterId],
    queryFn: () => api.readerChapter(id, chapterId as number),
    enabled: Boolean(id) && chapterId !== null,
  })

  const blocks = useQuery({
    queryKey: ['reader-blocks', id, chapterId],
    queryFn: () => api.readerBlocks(id, chapterId as number),
    enabled: (mode === 'bilingual' || mode === 'columns') && Boolean(id) && chapterId !== null,
  })

  // A partial, FLAT patch: the backend keeps only keys in READING_DEFAULTS,
  // so this merges server-side instead of clobbering untouched settings.
  const save = useMutation({
    mutationFn: (next: Partial<ReadingSettings>) => api.updateReaderSettings(next),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['reader-settings'] }),
  })

  const glossTerms = useQuery({
    queryKey: ['reader-glossary', id],
    queryFn: () => api.readerGlossary(id),
    // The snapshot never changes mid-read: fetch once per book and reuse it
    // across chapters, like the Python `glossReady` flag.
    enabled: Boolean(id) && glossary,
    staleTime: 300_000,
  })
  const terms = useMemo(
    () => prepareGlossTerms(glossTerms.data?.items),
    [glossTerms.data],
  )

  // One way to open a chapter: reset the view, remember the spot locally
  // (chapter + read tick + frac) and on the server (chapter), all
  // fire-and-forget — a failed persist must never block reading.
  const openChapter = (next: number) => {
    setSelectedId(next)
    if (scrollRef.current) scrollRef.current.scrollTop = 0
    const read = readIds.includes(next) ? readIds : [...readIds, next]
    setReadByBook((previous) => ({ ...previous, [id]: read }))
    writeJson(readKey(id), read)
    writeJson(locationKey(id), { chapter: next, frac: 0 })
    void save.mutate({ reading_last_location: { job_id: id, chapter: next } })
  }

  // Track the scroll fraction (rAF-throttled) and persist it debounced,
  // mirroring the Python reader's 500ms saveLoc.
  useEffect(() => {
    const element = scrollRef.current
    if (!element || chapterId === null) return
    let raf = 0
    const key = `${id}:${chapterId}`
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const max = element.scrollHeight - element.clientHeight
        const current = max > 0 ? element.scrollTop / max : 0
        setFracByKey((previous) => ({ ...previous, [key]: current }))
        window.clearTimeout(fracTimer.current)
        fracTimer.current = window.setTimeout(() => {
          writeJson(locationKey(id), { chapter: chapterId, frac: current })
        }, 500)
      })
    }
    element.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      element.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(raf)
      window.clearTimeout(fracTimer.current)
    }
  }, [id, chapterId])

  // Restore the remembered scroll position once the chapter DOM exists.
  // Only the scroll is set imperatively; the progress state follows from
  // the scroll event it fires, so no state is set inside this effect.
  useEffect(() => {
    const element = scrollRef.current
    if (!element || !content.data || chapterId === null) return
    const saved = loadSavedFrac(id, chapterId)
    if (saved === null || saved <= 0) return
    const timer = window.setTimeout(() => {
      const max = element.scrollHeight - element.clientHeight
      if (max > 0) element.scrollTop = saved * max
    }, 150)
    return () => window.clearTimeout(timer)
  }, [id, chapterId, content.data])

  // Highlight after every render that replaces the chapter DOM. Clearing
  // first keeps mode/chapter switches from double-wrapping; toggling the
  // switch off clears without re-marking.
  useEffect(() => {
    const root = scrollRef.current
    if (!root) return
    clearGlossMarks(root)
    if (!glossary || terms.length === 0) return
    applyGlossMarks(root, terms, mode, t('reader.glossary'))
  }, [content.data, blocks.data, mode, chapterId, terms, glossary, t])

  const items = chapterItems

  return (
    <main className="page" dir={dir}>
      <header className="mb-5">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
          {chapters.data?.book ?? t('reader.read')}
        </h1>
      </header>

      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        {/* ---- chapter list ---- */}
        <nav className="surface-card h-fit p-3" aria-label={t('reader.chapters')}>
          <h2 className="px-2 py-1 text-[length:var(--text-label)] font-bold">{t('reader.chapters')}</h2>
          {chapters.isPending ? (
            <div className="skeleton" style={{ height: 120 }} />
          ) : items.length === 0 ? (
            <p className="empty">{t('reader.noChapters')}</p>
          ) : (
            <ul className="grid gap-0.5" style={{ maxHeight: '65vh', overflow: 'auto' }}>
              {items.map((chapter: Chapter) => (
                <li key={chapter.id}>
                  <button
                    type="button"
                    className="w-full rounded-[var(--radius-control)] px-3 py-2 text-start text-[length:var(--text-small)]"
                    style={{
                      background: chapter.id === chapterId ? 'var(--color-primary-subtle)' : 'transparent',
                      color:
                        chapter.id === chapterId
                          ? 'var(--color-text-brand)'
                          : 'var(--color-text-secondary)',
                    }}
                    onClick={() => openChapter(chapter.id)}
                  >
                    {chapter.title}
                    {readIds.includes(chapter.id) ? (
                      <span aria-hidden="true"> ✓</span>
                    ) : null}
                    {readIds.includes(chapter.id) ? (
                      <span className="sr-only">{t('reader.readTick')}</span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        {/* ---- reader ---- */}
        <section className="grid gap-3">
          <div className="surface-card flex flex-wrap items-center gap-3 p-3">
            <div className="flex gap-1" role="group" aria-label={t('reader.mode.label')}>
              {READER_MODES.map((value) => (
                <button
                  key={value}
                  type="button"
                  className="btn btn-ghost"
                  aria-pressed={mode === value}
                  style={
                    mode === value
                      ? { background: 'var(--color-primary-subtle)', color: 'var(--color-text-brand)' }
                      : undefined
                  }
                  onClick={() => {
                    setModeOverride(value)
                    void save.mutate({ reading_mode: value })
                  }}
                >
                  {t(MODE_KEY[value])}
                </button>
              ))}
            </div>

            <label className="ms-auto flex items-center gap-2">
              <span className="label">{t('reader.fontSize')}</span>
              <input
                type="range"
                min={13}
                max={26}
                value={fontSize}
                onChange={(event) => {
                  const value = clampFontSize(Number(event.target.value))
                  setFontOverride(value)
                  void save.mutate({ reading_font_size: value })
                }}
                aria-label={t('reader.fontSize')}
              />
            </label>

            <label className="flex items-center gap-2">
              <span className="label">{t('reader.lineHeight')}</span>
              <select
                className="field"
                value={lineHeight}
                onChange={(event) => {
                  const value = clampLineHeight(Number(event.target.value))
                  setLeadingOverride(value)
                  void save.mutate({ reading_line_height: value })
                }}
                aria-label={t('reader.lineHeight')}
              >
                {LINE_HEIGHT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="label">{t('reader.width')}</span>
              <select
                className="field"
                value={width}
                onChange={(event) => {
                  const value = clampWidth(Number(event.target.value))
                  setWidthOverride(value)
                  void save.mutate({ reading_width: value })
                }}
                aria-label={t('reader.width')}
              >
                {WIDTH_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="label">{t('reader.direction')}</span>
              <select
                className="field"
                value={direction}
                onChange={(event) => {
                  const value = event.target.value
                  if (!isDirection(value)) return
                  setDirectionOverride(value)
                  void save.mutate({ reading_direction: value })
                }}
                aria-label={t('reader.direction')}
              >
                {DIRECTION_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {t(DIRECTION_KEY[option] ?? 'reader.direction.auto')}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={glossary}
              onClick={() => {
                setGlossOverride(!glossary)
                void save.mutate({ reading_glossary: !glossary })
              }}
            >
              {t('reader.glossary')}: {glossary ? t('reader.glossary.on') : t('reader.glossary.off')}
            </button>
          </div>

          {/* Overall progress: the fraction through this chapter added to the
              chapters before it, mirroring the Python `#progress-fill`. */}
          <div
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t('reader.progress', {
              index: fa(chapterIndex + 1),
              total: fa(items.length),
              percent: fa(percent),
            })}
            className="h-1.5 w-full overflow-hidden rounded-full"
            style={{ background: 'var(--color-surface-sunken)' }}
          >
            <div
              className="h-full rounded-full"
              style={{ width: `${percent}%`, background: 'var(--color-primary)' }}
            />
          </div>

          <article
            ref={scrollRef}
            className="surface-card mx-auto w-full p-6"
            style={{ maxHeight: '70vh', overflow: 'auto', fontSize, lineHeight, maxWidth: width }}
          >
            {content.isPending ? (
              <div className="skeleton" style={{ height: 320 }} />
            ) : content.isError ? (
              <p role="alert" className="alert alert-error">
                {t('reader.loadError')}
              </p>
            ) : (
              <ChapterBody
                content={content.data}
                mode={mode}
                direction={direction}
                blocks={blocks.data?.items ?? []}
                blocksPending={blocks.isPending}
              />
            )}
          </article>

          {items.length > 1 && chapterId !== null ? (
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={chapterId <= items[0]!.id}
                onClick={() => {
                  const index = items.findIndex((item) => item.id === chapterId)
                  const previous = items[Math.max(0, index - 1)]
                  if (previous) openChapter(previous.id)
                }}
              >
                {t('reader.prev')}
              </button>
              <span
                className="text-[length:var(--text-label)] tabular-nums"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {t('reader.progress', {
                  index: fa(chapterIndex + 1),
                  total: fa(items.length),
                  percent: fa(percent),
                })}
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={chapterId >= items[items.length - 1]!.id}
                onClick={() => {
                  const index = items.findIndex((item) => item.id === chapterId)
                  const next = items[Math.min(items.length - 1, index + 1)]
                  if (next) openChapter(next.id)
                }}
              >
                {t('reader.next')}
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  )
}

function ChapterBody({
  content,
  mode,
  direction,
  blocks,
  blocksPending,
}: {
  content: ChapterContent
  mode: ReaderMode
  direction: string
  blocks: ChapterBlock[]
  blocksPending: boolean
}) {
  const { t } = useLanguage()
  // Bilingual uses the block list so source and translation sit side by side.
  // The single-language modes use the chapter HTML directly, which is already
  // sanitised on the Python side. `columns` renders as bilingual until the
  // columns step lands its own paired layout.
  if (mode === 'bilingual' || mode === 'columns') {
    if (blocksPending) return <div className="skeleton" style={{ height: 320 }} />
    if (blocks.length === 0) {
      return (
        <p className="empty">
          {t('reader.noBilingual')}
        </p>
      )
    }
    return (
      <div className="grid gap-5">
        {blocks.map((block) => (
          <div key={block.id} className="grid gap-3 md:grid-cols-2">
            {/* Both are sanitised server-side. See the note at the top. Both
                also repeat the title as loose text and again in an <h1>, so
                each side is stripped on its own: the original and the
                translation carry different titles. `data-gloss-side` tells
                the highlighter which language each side is in; the direction
                of each side is detected from its own text. */}
            <div className="grid min-w-0 gap-1">
              <span
                className="block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {t('reader.side.original')}
              </span>
              <div
                dir={directionFor(block.original_html, direction)}
                data-gloss-side="source"
                className="leading-8"
                style={{ color: 'var(--color-text-secondary)' }}
                dangerouslySetInnerHTML={{ __html: stripDuplicatedHeading(block.original_html) }}
              />
            </div>
            <div className="grid min-w-0 gap-1">
              <span
                className="block text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {t('reader.side.translation')}
              </span>
              <div
                dir={directionFor(block.translation_html, direction)}
                data-gloss-side="target"
                className="leading-8"
                style={{ color: 'var(--color-text-primary)' }}
                dangerouslySetInnerHTML={{ __html: stripDuplicatedHeading(block.translation_html) }}
              />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      dir={directionFor(content.html, direction)}
      className="leading-8"
      style={{ color: 'var(--color-text-primary)' }}
      /* The chapter HTML repeats the title as loose text before the <h1>, so
         it renders twice. The page header already shows the title. */
      dangerouslySetInnerHTML={{
        __html: stripLeadingTitle(stripDuplicatedHeading(content.html), content.title),
      }}
    />
  )
}
