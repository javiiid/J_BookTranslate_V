import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Chapter, ChapterBlock, ChapterContent } from '@/lib/api'
import { stripDuplicatedHeading, stripLeadingTitle } from '@/lib/chunks'
import { fa } from '@/lib/format'

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

const MODE_FA: Record<ReadingSettings['reading_mode'], string> = {
  translation: 'ترجمه',
  original: 'مبدأ',
  bilingual: 'دوزبانه',
}

/** The subset of reader settings this page reads. */
interface ReadingSettings {
  reading_mode: 'translation' | 'original' | 'bilingual'
  reading_theme: 'light' | 'dark'
  reading_font_size: number
  reading_line_height: number
  reading_width: number
  reading_direction: 'auto' | 'ltr' | 'rtl'
}

export function ReaderPage() {
  const { id = '' } = useParams()
  const client = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [mode, setMode] = useState<ReadingSettings['reading_mode']>('bilingual')
  const [fontSize, setFontSize] = useState(17)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const settings = useQuery({
    queryKey: ['reader-settings'],
    queryFn: () => api.readerSettings(),
    staleTime: 300_000,
  })

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
    enabled: mode === 'bilingual' && Boolean(id) && chapterId !== null,
  })

  const save = useMutation({
    mutationFn: (next: Partial<ReadingSettings>) =>
      api
        .readerSettings()
        .then(() => request('PUT', '/api/reader/settings', { value: { ...current, ...next } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['reader-settings'] }),
  })

  const current: ReadingSettings = {
    reading_mode: (settings.data?.value?.reading_mode as ReadingSettings['reading_mode']) ?? 'bilingual',
    reading_theme: 'light',
    reading_font_size: fontSize,
    reading_line_height: 1.9,
    reading_width: 720,
    reading_direction: 'auto',
  }

  async function request(method: string, path: string, body: unknown) {
    const response = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  }

  const items = chapters.data?.items ?? []

  return (
    <main className="page" dir="rtl">
      <header className="mb-5">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
          {chapters.data?.book ?? 'مطالعه'}
        </h1>
      </header>

      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        {/* ---- chapter list ---- */}
        <nav className="surface-card h-fit p-3" aria-label="فصل‌ها">
          <h2 className="px-2 py-1 text-[length:var(--text-label)] font-bold">فصل‌ها</h2>
          {chapters.isPending ? (
            <div className="skeleton" style={{ height: 120 }} />
          ) : items.length === 0 ? (
            <p className="empty">فصلی برای این کتاب یافت نشد.</p>
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
            <div className="flex gap-1" role="group" aria-label="حالت نمایش">
              {(Object.keys(MODE_FA) as ReadingSettings['reading_mode'][]).map((value) => (
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
                  onClick={() => setMode(value)}
                >
                  {MODE_FA[value]}
                </button>
              ))}
            </div>

            <label className="ms-auto flex items-center gap-2">
              <span className="label">اندازهٔ متن</span>
              <input
                type="range"
                min={13}
                max={26}
                value={fontSize}
                onChange={(event) => {
                  const value = Number(event.target.value)
                  setFontSize(value)
                  void save.mutate({ reading_font_size: value })
                }}
                aria-label="اندازهٔ متن"
              />
            </label>
          </div>

          <article
            ref={scrollRef}
            className="surface-card p-6"
            style={{ maxHeight: '70vh', overflow: 'auto', fontSize }}
          >
            {content.isPending ? (
              <div className="skeleton" style={{ height: 320 }} />
            ) : content.isError ? (
              <p role="alert" className="alert alert-error">
                بارگذاری این فصل ممکن نشد.
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
                فصل قبل
              </button>
              <span
                className="text-[length:var(--text-label)] tabular-nums"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {fa(items.findIndex((item) => item.id === chapterId) + 1)} از {fa(items.length)}
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
                فصل بعد
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
  mode: ReadingSettings['reading_mode']
  blocks: ChapterBlock[]
  blocksPending: boolean
}) {
  // Bilingual uses the block list so source and translation sit side by side.
  // The single-language modes use the chapter HTML directly, which is already
  // sanitised on the Python side.
  if (mode === 'bilingual') {
    if (blocksPending) return <div className="skeleton" style={{ height: 320 }} />
    if (blocks.length === 0) {
      return (
        <p className="empty">
          این فصل به‌صورت دوزبانه هم‌تراز نشده است؛ حالت «ترجمه» را امتحان کنید.
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
