import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Chapter, ChapterBlock, ChapterContent, ReadingSettings } from '@/lib/api'
import { stripDuplicatedHeading, stripLeadingTitle } from '@/lib/chunks'
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
  isDirection,
  toReaderMode,
  type ReaderMode,
} from '@/lib/reading.ts'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { StringKey } from '@/i18n/fa.ts'

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

  // Derived, not stored in state via an effect. An effect that sets the chapter
  // on first load costs an extra render, and if it re-runs on a refetch it
  // silently yanks the reader back to chapter one. Falling back to the first
  // chapter here has neither problem.
  const firstChapterId = chapters.data?.items[0]?.id ?? null
  const chapterId = selectedId ?? firstChapterId

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

  const items = chapters.data?.items ?? []

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
                    onClick={() => {
                      setSelectedId(chapter.id)
                      if (scrollRef.current) scrollRef.current.scrollTop = 0
                    }}
                  >
                    {chapter.title}
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
                  if (previous) setSelectedId(previous.id)
                }}
              >
                {t('reader.prev')}
              </button>
              <span
                className="text-[length:var(--text-label)] tabular-nums"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {t('reader.position', {
                  index: fa(items.findIndex((item) => item.id === chapterId) + 1),
                  total: fa(items.length),
                })}
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={chapterId >= items[items.length - 1]!.id}
                onClick={() => {
                  const index = items.findIndex((item) => item.id === chapterId)
                  const next = items[Math.min(items.length - 1, index + 1)]
                  if (next) setSelectedId(next.id)
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
  blocks,
  blocksPending,
}: {
  content: ChapterContent
  mode: ReaderMode
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
                translation carry different titles. */}
            <div
              dir="ltr"
              className="leading-8"
              style={{ color: 'var(--color-text-secondary)' }}
              dangerouslySetInnerHTML={{ __html: stripDuplicatedHeading(block.original_html) }}
            />
            <div
              dir="rtl"
              className="leading-8"
              style={{ color: 'var(--color-text-primary)' }}
              dangerouslySetInnerHTML={{ __html: stripDuplicatedHeading(block.translation_html) }}
            />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      dir={mode === 'translation' ? 'rtl' : 'ltr'}
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
