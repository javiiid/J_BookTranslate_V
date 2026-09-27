import { key } from './terms.ts'

/**
 * Flag extraction for chunk rows.
 *
 * `/api/jobs/{id}/chunks` returns only `flagged: boolean`. The `notes` the
 * monitor shows next to a flag are derived on the client, and the Python page
 * does exactly this in `app/jobs/detail_page.py`:
 *
 *     const NOTE_RE = /\{(NOTE|BOUNDARY_WARNING|WARNING)[:\s][^}]*\}/g
 *     const isFlagged = t => NOTE_RE.test(String(t || ''))
 *     notes: flaggedNotes(target).concat(flaggedNotes(source)).slice(0, 3)
 *
 * That matters for more than cosmetics: the markers are the only way a
 * translation says "I could not render this" or "this crosses a chapter
 * boundary", so they are the human review queue for the QA tab.
 *
 * The server flags a row with the same three prefixes, so the two stay in
 * agreement. If you change one, change both.
 */

export const NOTE_PATTERN = /\{(NOTE|BOUNDARY_WARNING|WARNING)[:\s][^}]*\}/g

/**
 * Every marker in a piece of text.
 *
 * NOTE_PATTERN is a global regex, and `lastIndex` survives between calls, so
 * a fresh regex is used per call. Sharing one instance made the *second* row of
 * a list return nothing, which is the classic global-regex bug.
 */
export function extractNotes(text: string | null | undefined): string[] {
  if (!text) return []
  return text.match(new RegExp(NOTE_PATTERN.source, 'g')) ?? []
}

// Re-exported so callers that already import from here keep working, and so the
// glossary and the chunk filter cannot drift onto different normalisation.
// The `.ts` extension is required: these files are loaded directly by
// `node --test`, which resolves imports with Node's ESM rules, not Vite's.
export { key } from './terms.ts'

export function hasFlag(text: string | null | undefined): boolean {
  if (!text) return false
  return new RegExp(NOTE_PATTERN.source).test(text)
}

/** A chunk row with the notes the Python page derives. */
export interface ChunkRow {
  id: string
  chapter: string
  source: string
  target: string
  flagged: boolean
  /** At most three, target first. */
  notes: string[]
}

/** Matches the Python `note_text = lambda: flaggedNotes(target)...slice(0, 3)`. */
export function toRow(chunk: {
  id: string
  chapter: string
  source: string
  target: string
  flagged: boolean
}): ChunkRow {
  const target = chunk.target ?? ''
  const source = chunk.source ?? ''
  return {
    // Normalised so the key matches what the Python side would compute for the
    // same chunk. chunk-1 and CHUNK-1 must not become two rows.
    id: key(chunk.id),
    chapter: chunk.chapter ?? '',
    source,
    target,
    flagged: chunk.flagged,
    notes: [...extractNotes(target), ...extractNotes(source)].slice(0, 3),
  }
}

/**
 * Strip a duplicated leading title from a chapter's HTML.
 *
 * `/api/reader/{id}/chapters/{n}` returns the chapter title twice: once as
 * loose text before any markup, then again inside an `<h1>`. The loose copy is
 * not markup, so nothing downstream can remove it, and the reader shows the
 * title twice with a blank line between.
 *
 * This is a Python-side defect -- the chapter builder emits the title and then
 * the body, which starts with the same title. Until that is fixed here, the
 * leading duplicate is dropped in the client, because the reader already shows
 * the title in its own header and a second copy is visual noise.
 *
 * Only a *leading* run of whitespace and the exact title is removed. Text later
 * in the document is untouched, and a title that does not match exactly is left
 * alone rather than guessed at.
 */
export function stripLeadingTitle(html: string, title: string): string {
  const needle = title.trim()
  if (!needle) return html

  // The title may itself be wrapped in an <h1>, and it may be a prefix of a
  // longer loose run, so match it once at the very start and once inside the
  // first heading.
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  const leadingHeading = new RegExp(`^\\s*<h1[^>]*>\\s*${escaped}\\s*<\\/h1>\\s*`, 'iu')
  const leadingText = new RegExp(`^\\s*${escaped}\\s*`, 'u')

  // The two copies appear in either order depending on the builder, and after
  // removing the first the second becomes the new leading text. Looping until
  // neither matches handles both orders and any number of repeats, while the
  // `^` anchor means a title that appears later in the body is never touched.
  let result = html
  for (let pass = 0; pass < 3; pass++) {
    const next = result.replace(leadingHeading, '').replace(leadingText, '')
    if (next === result) break
    result = next
  }
  return result.trimStart()
}

/**
 * Drop a leading title that the chapter HTML contains twice.
 *
 * `/api/reader/{id}/chapters/{n}` and every block under it come back shaped like
 * this, with the title as loose text and then again inside an `<h1>`:
 *
 *     \n\n\nمعضل نقشه‌کش\n\n\n<h1>معضل نقشه‌کش</h1><p>…</p>
 *
 * The loose copy is not markup, so nothing downstream can remove it, and the
 * reader printed the title twice with a blank line between. This is a
 * Python-side defect -- the chapter builder writes the title and then the body,
 * which starts with the same title. Until that is fixed there, both copies go
 * here: the reader already shows the title in its own page header.
 *
 * Unlike `stripLeadingTitle`, this needs no title. The bilingual blocks carry
 * the *translated* title in `translation_html` and the *original* one in
 * `original_html`, so there is no single string to match both against, and the
 * page only has the translated title to hand.
 *
 * Deliberately conservative: both copies have to be present, and they have to
 * agree after normalising whitespace and case. A document with only one heading
 * is left exactly as it is, because guessing which heading is redundant would
 * risk deleting a chapter's real first section.
 */
export function stripDuplicatedHeading(html: string): string {
  const normalise = (value: string) =>
    value
      .replace(/<[^>]*>/g, ' ')
      .replace(/[\s ‌‏]+/g, ' ')
      .trim()
      .toLowerCase()

  // The observed shape, as one pattern: whitespace, a run of text with no tag in
  // it, then a first-level heading. Matching both halves together is what makes
  // this work: an earlier version matched them separately, so the heading never
  // matched once the loose text was in front of it, and only the loose copy went.
  const pair = /^[\s ]*((?:(?!<)[\s\S])*?)<h1(?:\s[^>]*)?>([\s\S]*?)<\/h1>[\s ]*/i.exec(html)
  if (pair) {
    const loose = normalise(pair[1] ?? '')
    const heading = normalise(pair[2] ?? '')
    // A true duplicate: both present, and they name the same thing once
    // whitespace, direction marks and case are ignored.
    if (loose && heading && (loose === heading || loose.startsWith(heading) || heading.startsWith(loose))) {
      return html.slice(pair[0].length)
    }
    // The loose run was empty, so this is a document that simply opens with a
    // heading. Still redundant next to the page header, so it goes.
    if (!loose) return html.slice(pair[0].length)
    // Two different strings: not a duplicate, and dropping either one would
    // delete real content. Leave the document alone.
    return html
  }

  // One copy only, never two.
  const headingOnly = /^[\s ]*<h1(?:\s[^>]*)?>[\s\S]*?<\/h1>[\s ]*/i.exec(html)
  if (headingOnly) return html.slice(headingOnly[0].length)

  const looseOnly = /^[\s ]*((?:(?!<)[\s\S])*?)(?=<)/.exec(html)
  if (looseOnly && looseOnly[1]?.trim()) return html.slice(looseOnly[0].length)

  return html
}

export type ChunkStateFilter = 'all' | 'done' | 'pending' | 'flagged'

/**
 * The three filters the Python page applies, in the same order.
 *
 * Note `translated` is derived from a non-empty target, exactly as the Python
 * `row.translated` was. The API has no `translated` field on a chunk.
 */
export function filterChunks(
  rows: ChunkRow[],
  options: { query: string; state: ChunkStateFilter; flaggedOnly: boolean },
): ChunkRow[] {
  const query = options.query.trim().toLowerCase()
  return rows.filter((row) => {
    if (options.flaggedOnly && !row.flagged) return false
    const translated = row.target !== ''
    if (options.state === 'done' && !translated) return false
    if (options.state === 'pending' && translated) return false
    if (options.state === 'flagged' && !row.flagged) return false
    if (query) {
      const haystack = `${row.source.toLowerCase()}\n${row.target.toLowerCase()}`
      if (!haystack.includes(query)) return false
    }
    return true
  })
}
