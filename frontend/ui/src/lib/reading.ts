/**
 * Reading-setting decisions, asserted without a DOM.
 *
 * The bounds below mirror the server validation on
 * `PUT /api/reader/settings` (`app/web.py`), so the settings controls can
 * clamp instantly instead of waiting for the round trip. The server remains
 * authoritative and re-clamps everything; these only keep the slider and the
 * selects from ever offering a value the server would refuse.
 *
 * `node --test` has no DOM, so the decisions live here as plain functions
 * and `tests/reading.test.ts` drives them directly. The page keeps the
 * rendering and nothing else.
 */

import type { ReadingSettings } from './api.ts'

/** Display modes the reader port implements. */
export type ReaderMode = 'translation' | 'original' | 'bilingual' | 'columns'

/**
 * The mode for a stored value.
 *
 * Unknown values fall back to `bilingual` rather than the server's
 * `translation` default: this port opens on the paired view, and a mode the
 * client does not know must render something rather than nothing.
 */
export function toReaderMode(value: string | undefined): ReaderMode {
  return value === 'translation' ||
    value === 'original' ||
    value === 'bilingual' ||
    value === 'columns'
    ? value
    : 'bilingual'
}

/** The mode buttons, in the order the Python settings sheet lists them. */
export const READER_MODES: readonly ReaderMode[] = [
  'translation',
  'original',
  'bilingual',
  'columns',
]

/** Font sizes the Python sheet offers. The slider admits more; the server clamps to 14–30. */
export const FONT_SIZE_MIN = 14
export const FONT_SIZE_MAX = 30
export const FONT_SIZE_FALLBACK = 18

/** Line heights the Python sheet offers. The server clamps to 1.4–2.6. */
export const LINE_HEIGHT_OPTIONS: readonly number[] = [1.7, 1.9, 2.1]
export const LINE_HEIGHT_FALLBACK = 1.9

/** Content widths the Python sheet offers. The server clamps to 560–1000. */
export const WIDTH_OPTIONS: readonly number[] = [640, 760, 880]
export const WIDTH_FALLBACK = 760

/** Reading directions the Python sheet offers. */
export const DIRECTION_OPTIONS: readonly NonNullable<
  ReadingSettings['reading_direction']
>[] = ['auto', 'rtl', 'ltr']

function finiteOr(value: number, fallback: number): number {
  return Number.isFinite(value) ? value : fallback
}

/** Mirror of the server's `int()` clamp for `reading_font_size`. */
export function clampFontSize(value: number): number {
  const truncated = Math.trunc(finiteOr(value, FONT_SIZE_FALLBACK))
  return Math.min(FONT_SIZE_MAX, Math.max(FONT_SIZE_MIN, truncated))
}

/** Mirror of the server's `float()` clamp for `reading_line_height`. */
export function clampLineHeight(value: number): number {
  return Math.min(2.6, Math.max(1.4, finiteOr(value, LINE_HEIGHT_FALLBACK)))
}

/** Mirror of the server's `int()` clamp for `reading_width`. */
export function clampWidth(value: number): number {
  const truncated = Math.trunc(finiteOr(value, WIDTH_FALLBACK))
  return Math.min(1000, Math.max(560, truncated))
}

/**
 * Whether a direction value may be sent to the server.
 *
 * Anything else is a 400-shaped refusal folded into `auto` server-side, so
 * the select is built from `DIRECTION_OPTIONS` rather than free text.
 */
export function isDirection(
  value: string,
): value is NonNullable<ReadingSettings['reading_direction']> {
  return value === 'auto' || value === 'rtl' || value === 'ltr'
}

/* ------------------------------------------------------------------ */
/* Paragraph pairing and reading progress                               */
/* ------------------------------------------------------------------ */

/**
 * Local storage keys, shared with the Python reader (`app/reader/page.py`):
 * a location survives switching between the two readers because both read
 * and write the same keys.
 */
export function locationKey(jobId: string): string {
  return `jbook:loc:${jobId}`
}

export function readKey(jobId: string): string {
  return `jbook:read:${jobId}`
}

/**
 * Content direction for one side, mirroring `directionFor()` in
 * `app/reader/page.py`: an explicit setting wins, otherwise any Arabic-
 * script character (U+0600–U+06FF) makes it RTL. Unknown settings fall
 * through to detection rather than rendering nothing.
 */
export function directionFor(html: string, direction: string): 'rtl' | 'ltr' {
  if (direction === 'rtl' || direction === 'ltr') return direction
  return /[\u0600-\u06FF]/.test(html) ? 'rtl' : 'ltr'
}

/**
 * Overall reading progress in whole percent: the fraction through the
 * current chapter added to the chapters before it. Clamped, never NaN —
 * an empty book reports 0 rather than dividing by zero.
 */
export function overallPercent(index: number, frac: number, total: number): number {
  if (!Number.isFinite(index) || !Number.isFinite(frac) || !(total > 0)) return 0
  const clamped = Math.min(1, Math.max(0, frac))
  return Math.min(100, Math.max(0, Math.round(((index + clamped) / total) * 100)))
}

/**
 * The chapter the server remembers, or `null` when it remembers nothing
 * usable. The stored shape is `{job_id, chapter}` (written by the Python
 * reader and by this port); anything else — the default `null`, a stray
 * string from an older build — is "no memory", not an error.
 */
export function lastLocationOf(value: unknown): { chapter: number } | null {
  if (typeof value !== 'object' || value === null) return null
  const chapter = (value as { chapter?: unknown }).chapter
  if (typeof chapter !== 'number' || !Number.isFinite(chapter) || chapter < 0) {
    return null
  }
  return { chapter: Math.trunc(chapter) }
}

/**
 * Which chapter to open: an explicit choice first, then the locally
 * remembered chapter when it still exists, then the server memory, else
 * nothing (the caller falls back to the first chapter).
 */
export function storedChapter(
  validIds: ReadonlyArray<number>,
  selected: number | null,
  local: unknown,
  server: unknown,
): number | null {
  if (selected !== null && validIds.includes(selected)) return selected
  const localChapter = lastLocationOf(local)
  if (localChapter !== null && validIds.includes(localChapter.chapter)) {
    return localChapter.chapter
  }
  const serverChapter = lastLocationOf(server)
  if (serverChapter !== null && validIds.includes(serverChapter.chapter)) {
    return serverChapter.chapter
  }
  return null
}
