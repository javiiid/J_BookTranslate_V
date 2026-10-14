/**
 * Reader glossary highlighting decisions, asserted without a DOM.
 *
 * The data comes from `GET /api/reader/:id/glossary`: the job's own
 * snapshot — the same terms the book was translated with — longest source
 * first, capped at 40 server-side (`job_glossary_terms` in
 * `app/reader/service.py`). This module re-pins those rules client-side
 * rather than trusting the order on the wire, the way `activeVariant` in
 * `lib/library.ts` does not trust variant ordering.
 *
 * `node --test` has no DOM, so everything here is pure: term preparation,
 * case-insensitive search with an NFKC fallback, and side-aware tip
 * selection. The TreeWalker walk that applies them lives in
 * `ReaderPage.tsx`, next to the markup it mutates.
 */

export interface GlossTerm {
  source: string
  target: string
}

/** Server cap, mirrored so the client never asks for more than exists. */
export const MAX_GLOSS_TERMS = 40
/** Python `applyGloss` stops at 200 marks per chapter; so does the port. */
export const MAX_GLOSS_MARKS = 200
/** Python slices the tooltip side to 60 chars; so does the port. */
export const GLOSS_TARGET_SLICE = 60

export interface RawGlossTerm {
  source_term: string
  target_term: string
}

/**
 * The terms worth highlighting, longest source first.
 *
 * Empty sides are dropped (a mark with no text to find would match
 * everywhere), the tip side is sliced like Python's, and the sort is
 * longest-first so a specific phrase wins over its own prefix. `Array.sort`
 * is stable, so equal lengths keep the server's order.
 */
export function prepareGlossTerms(
  items: ReadonlyArray<RawGlossTerm> | null | undefined,
  limit: number = MAX_GLOSS_TERMS,
): GlossTerm[] {
  if (!items) return []
  const cleaned: GlossTerm[] = []
  for (const item of items) {
    const source = (item?.source_term ?? '').trim()
    const target = (item?.target_term ?? '').trim().slice(0, GLOSS_TARGET_SLICE)
    if (source && target) cleaned.push({ source, target })
  }
  cleaned.sort((a, b) => b.source.length - a.source.length)
  return cleaned.slice(0, Math.max(0, limit))
}

/**
 * Normalized text plus, for each normalized offset, the original offset it
 * came from. Iterates UTF-16 units because `splitText` counts in UTF-16 —
 * a code-point walk would misplace every mark past an emoji.
 */
function normIndexMap(text: string): { norm: string; map: number[] } {
  let norm = ''
  const map: number[] = []
  for (let i = 0; i < text.length; i++) {
    // Lone surrogates normalize to themselves, so splitting a pair and
    // rejoining is lossless for mapping purposes.
    const piece = text[i]!.normalize('NFKC')
    for (let j = 0; j < piece.length; j++) map.push(i)
    norm += piece
  }
  return { norm, map }
}

/**
 * First occurrence of `source` in `text` at or after `fromIndex`.
 *
 * Case-insensitive on the original first; on a miss, case-insensitive on
 * the NFKC forms (half-spaces, fullwidth and ligature forms) with the hit
 * mapped back to original offsets, so the mark wraps the on-screen casing.
 * Returns `null` for an empty needle — it would match everywhere.
 */
export function findTermAt(
  text: string,
  source: string,
  fromIndex = 0,
): { index: number; length: number } | null {
  if (!source) return null
  const start = Math.max(0, fromIndex)
  const needle = source.toLowerCase()
  const direct = text.toLowerCase().indexOf(needle, start)
  if (direct >= 0) return { index: direct, length: source.length }
  const { norm, map } = normIndexMap(text.toLowerCase())
  const normNeedle = needle.normalize('NFKC')
  if (!normNeedle) return null
  // `start` is an original offset; count how many normalized units precede it.
  let normStart = 0
  while (normStart < map.length && map[normStart]! < start) normStart++
  const found = norm.indexOf(normNeedle, normStart)
  if (found < 0) return null
  const index = map[found]!
  const end = found + normNeedle.length
  const length = (end < map.length ? map[end]! : text.length) - index
  if (length <= 0) return null
  return { index, length }
}

/** Which language the marked text is in. */
export type GlossSide = 'source' | 'target'

/** The text to match in a node of the given side. */
export function textFor(term: GlossTerm, side: GlossSide): string {
  return side === 'source' ? term.source : term.target
}

/**
 * The tooltip for a mark on the given side: always the *other* language.
 * A mark that explained its own side would restate what is on screen.
 */
export function tipFor(term: GlossTerm, side: GlossSide): string {
  return side === 'source' ? term.target : term.source
}
