/**
 * Tests for the pure logic behind the job monitor.
 *
 * No DOM, no React: the window arithmetic and the chunk filters are the two
 * places where a mistake is invisible at a glance. A virtualiser with an
 * off-by-one still renders a table, just with a gap of blank space at the end
 * of a long book, and a filter with the wrong precedence silently shows rows
 * the user excluded.
 *
 * Run with: npm test
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { type ChunkRow, extractNotes, filterChunks, stripDuplicatedHeading, stripLeadingTitle, toRow } from '../src/lib/chunks.ts'
import { OVERSCAN, ROW_H, computeWindow, scrollToReveal } from '../src/lib/virtual.ts'

const rows = (count: number): ChunkRow[] =>
  Array.from({ length: count }, (_, index) => ({
    id: `chunk-${index}`,
    chapter: index % 2 === 0 ? 'فصل ۱' : '',
    source: `source text ${index}`,
    target: index % 3 === 0 ? '' : `متن ترجمه ${index}`,
    flagged: index % 7 === 0,
    notes: [],
  }))

describe('computeWindow', () => {
  it('renders only a small slice of a long list', () => {
    const result = computeWindow(rows(4000), 0, 520)
    // 520 / 96 = 5.4 -> 6 visible, plus 6 overscan each side.
    assert.equal(result.rows.length, 6 + OVERSCAN * 2)
    assert.ok(result.rows.length < 30, 'a 4000-row book must not render 4000 rows')
  })

  it('starts at the first row with no top spacer at scroll zero', () => {
    const result = computeWindow(rows(500), 0, 520)
    assert.equal(result.start, 0)
    assert.equal(result.padTop, 0)
  })

  it('keeps the scroll height honest, so the scrollbar matches the real length', () => {
    const list = rows(1000)
    const result = computeWindow(list, 0, 520)
    // Top spacer + rendered rows + bottom spacer must account for every row.
    const accountedFor =
      result.padTop / ROW_H + result.rows.length + result.padBottom / ROW_H
    assert.equal(accountedFor, list.length)
  })

  it('adds a top spacer once the user scrolls past the overscan', () => {
    const result = computeWindow(rows(1000), 96 * 30, 520)
    assert.equal(result.start, 30 - OVERSCAN)
    assert.equal(result.padTop, (30 - OVERSCAN) * ROW_H)
    assert.ok(result.padTop > 0)
  })

  it('still covers the viewport at the very end of the list', () => {
    const list = rows(50)
    const result = computeWindow(list, 10_000, 520)
    assert.equal(result.end, 50)
    assert.equal(result.padBottom, 0, 'no spacer below the last row')
    assert.ok(result.rows.length > 0, 'the final rows must be reachable')
  })

  it('never produces a negative spacer when the list is shorter than the window', () => {
    const result = computeWindow(rows(3), 0, 520)
    assert.equal(result.padTop, 0)
    assert.equal(result.padBottom, 0)
    assert.equal(result.rows.length, 3)
  })

  it('handles an empty list without throwing', () => {
    const result = computeWindow([], 500, 520)
    assert.deepEqual(result.rows, [])
    assert.equal(result.padTop, 0)
    assert.equal(result.padBottom, 0)
  })

  it('survives a negative scrollTop', () => {
    // Impossible in a DOM, easy to produce in a test, and a negative index
    // would slice from the end of the array.
    const result = computeWindow(rows(100), -500, 520)
    assert.equal(result.start, 0)
  })

  it('treats a zero-height viewport as one row rather than none', () => {
    const result = computeWindow(rows(100), 0, 0)
    assert.ok(result.rows.length >= 1)
  })

  it('reports how many rows are not painted', () => {
    const result = computeWindow(rows(1000), 0, 520)
    assert.equal(result.hidden, 1000 - result.rows.length)
  })

  it('keeps rendering when a filter shrinks the list under the scroll position', () => {
    // The realistic version of the bug: the reader is 300 rows down a
    // 1000-row book, then types a filter that leaves 4 rows. scrollTop is still
    // 28800, and slice(294, 4) would render nothing at all.
    const full = computeWindow(rows(1000), 96 * 300, 520)
    assert.ok(full.rows.length > 0)

    const filtered = filterChunks(rows(1000), {
      query: 'source text 1',
      state: 'all',
      flaggedOnly: false,
    })
    const after = computeWindow(filtered, 96 * 300, 520)
    assert.ok(after.rows.length > 0, 'rows must survive a filter that shrinks the list')
    assert.ok(after.padBottom >= 0)
  })

  it('never returns an empty render for a non-empty list', () => {
    // Property check: whatever the scroll position, a non-empty list shows at
    // least one row. This is the invariant the blank-table bug violated.
    const list = rows(50)
    for (const top of [0, 1, 95, 96, 4799, 4800, 99999, -50]) {
      const result = computeWindow(list, top, 520)
      assert.ok(result.rows.length > 0, `no rows rendered at scrollTop=${top}`)
      assert.ok(result.start >= 0 && result.end <= list.length, `bad range at scrollTop=${top}`)
    }
  })
})

describe('scrollToReveal', () => {
  it('leaves the position alone when the row is already visible', () => {
    assert.equal(scrollToReveal(3, 500, 0), 0)
  })

  it('scrolls up to a row above the viewport', () => {
    assert.equal(scrollToReveal(2, 500, 960), 2 * ROW_H)
  })

  it('scrolls down just far enough to show a row below the viewport', () => {
    const viewport = 500
    const target = 20 * ROW_H
    const next = scrollToReveal(20, viewport, 0)
    assert.ok(next <= target, 'must not overshoot past the row')
    assert.ok(next + viewport >= target + ROW_H, 'the row must be fully visible')
  })
})

describe('extractNotes', () => {
  it('finds a NOTE marker', () => {
    assert.deepEqual(extractNotes('متن {NOTE: ambiguous} پایان'), ['{NOTE: ambiguous}'])
  })

  it('finds BOUNDARY_WARNING and WARNING too', () => {
    assert.equal(extractNotes('{BOUNDARY_WARNING: split}')[0], '{BOUNDARY_WARNING: split}')
    assert.equal(extractNotes('{WARNING: check}')[0], '{WARNING: check}')
  })

  it('ignores a marker with no colon or space after the keyword', () => {
    // Matches the Python regex `[:\s]`, so `{NOTE}` alone is not a flag.
    assert.deepEqual(extractNotes('{NOTE}'), [])
  })

  it('is not affected by regex state leaking between calls', () => {
    // A shared global regex keeps lastIndex between calls, which made the
    // second row of a list come back empty.
    const text = 'a {NOTE: one} b {WARNING: two}'
    assert.equal(extractNotes(text).length, 2)
    assert.equal(extractNotes(text).length, 2)
    assert.equal(extractNotes(text).length, 2)
  })

  it('handles empty and nullish input', () => {
    assert.deepEqual(extractNotes(''), [])
    assert.deepEqual(extractNotes(null), [])
    assert.deepEqual(extractNotes(undefined), [])
  })
})

describe('toRow', () => {
  it('derives notes from the target first, then the source', () => {
    const row = toRow({
      id: 'c1',
      chapter: 'فصل ۱',
      source: 'src {NOTE: s}',
      target: 'tgt {WARNING: t}',
      flagged: true,
    })
    assert.deepEqual(row.notes, ['{WARNING: t}', '{NOTE: s}'])
  })

  it('keeps at most three notes, like the Python slice(0, 3)', () => {
    const row = toRow({
      id: 'c1',
      chapter: '',
      source: '{NOTE: a}{NOTE: b}{NOTE: c}',
      target: '{WARNING: d}{WARNING: e}{WARNING: f}',
      flagged: true,
    })
    assert.equal(row.notes.length, 3)
  })
})

/* ------------------------------------------------------------------ */
/* Chapter title duplication                                           */
/* ------------------------------------------------------------------ */

describe('stripLeadingTitle', () => {
  // The exact shape the live endpoint returns: the title as loose text, then
  // the same title inside an <h1>.
  const DUPLICATED = '\n\n\n\nمعضل نقشه\u200cکش\n\n\n\n<h1>معضل نقشه\u200cکش</h1>\n<p>متن</p>'

  /* BOTH copies are removed, not just the loose one. The reader shows the
     chapter title in its own page header, so leaving an <h1> as well would
     print it twice with a blank line between. That is the actual complaint
     this fixes. */
  it('removes both copies and leaves the body', () => {
    const result = stripLeadingTitle(DUPLICATED, 'معضل نقشه\u200cکش')
    assert.equal(result, '<p>متن</p>')
  })

  it('removes a lone heading', () => {
    assert.equal(stripLeadingTitle('<h1>Title</h1><p>Body</p>', 'Title'), '<p>Body</p>')
  })

  it('removes a lone loose copy', () => {
    assert.equal(stripLeadingTitle('Title<p>Body</p>', 'Title'), '<p>Body</p>')
  })

  it('handles three repeats', () => {
    const html = 'T<h1>T</h1>T<p>Body</p>'
    assert.equal(stripLeadingTitle(html, 'T'), '<p>Body</p>')
  })

  it('leaves a document alone when the title does not match', () => {
    // Guessing would delete real content, so an inexact match is left as it is.
    const html = '<h1>Something Else</h1><p>Body</p>'
    assert.equal(stripLeadingTitle(html, 'Title'), html)
  })

  it('only removes a title at the very start', () => {
    const html = '<p>Intro</p><p>The Title appears again</p>'
    assert.equal(stripLeadingTitle(html, 'The Title'), html)
  })

  it('tolerates an empty title', () => {
    assert.equal(stripLeadingTitle('<p>Body</p>', ''), '<p>Body</p>')
    assert.equal(stripLeadingTitle('<p>Body</p>', '   '), '<p>Body</p>')
  })

  it('does not treat the title as a regex', () => {
    // A title containing regex metacharacters must not blow up or match loosely.
    const html = '<h1>Chapter 1 (a+b) [x]</h1><p>Body</p>'
    assert.equal(stripLeadingTitle(html, 'Chapter 1 (a+b) [x]'), '<p>Body</p>')
    const loose = 'Chapter 1 (a+b) [x]<p>Body</p>'
    assert.equal(stripLeadingTitle(loose, 'Chapter 1 (a+b) [x]'), '<p>Body</p>')
  })

  it('is case insensitive on the heading, which some builders emit', () => {
    assert.equal(stripLeadingTitle('<h1>TITLE</h1><p>B</p>', 'Title'), '<p>B</p>')
  })

  it('leaves a heading that is not the chapter title', () => {
    const html = '<h1>Chapter 1</h1><p>The Cartographer’s Dilemma</p>'
    assert.equal(stripLeadingTitle(html, 'The Cartographer’s Dilemma'), html)
  })
})

describe('stripDuplicatedHeading', () => {
  /* The bilingual blocks carry the original title in one column and the
     translated title in the other, so no single title string fits both. This is
     what the live block payload looks like, both sides. */
  const ORIGINAL = '\n\n\n\nThe Cartographer\u2019s Dilemma\n\n\n\n<h1>The Cartographer\u2019s Dilemma</h1>\n<p>She unrolled</p>'
  const TRANSLATED = '\n\n\n\nمعضل نقشه\u200cکش\n\n\n\n<h1>معضل نقشه\u200cکش</h1>\n<p>نقشه را گشود</p>'

  it('removes the title from the original side', () => {
    const result = stripDuplicatedHeading(ORIGINAL)
    assert.equal(result, '<p>She unrolled</p>')
  })

  it('removes the title from the translated side', () => {
    const result = stripDuplicatedHeading(TRANSLATED)
    assert.equal(result, '<p>نقشه را گشود</p>')
  })

  it('handles the exact payload shape, with the trailing newline', () => {
    // The trailing newline is the document's own content, not title noise, so it
    // is kept. Only the title is removed.
    assert.equal(stripDuplicatedHeading(ORIGINAL + '\n'), '<p>She unrolled</p>\n')
  })

  it('removes a lone loose copy', () => {
    assert.equal(stripDuplicatedHeading('Title<p>Body</p>'), '<p>Body</p>')
  })

  it('removes a lone heading', () => {
    assert.equal(stripDuplicatedHeading('<h1>Title</h1><p>Body</p>'), '<p>Body</p>')
  })

  it('tolerates attributes on the heading', () => {
    assert.equal(
      stripDuplicatedHeading('Title<h1 class="x" id="y">Title</h1><p>Body</p>'),
      '<p>Body</p>',
    )
  })

  it('matches despite different internal whitespace', () => {
    assert.equal(
      stripDuplicatedHeading('A  B<h1>A\n B</h1><p>Body</p>'),
      '<p>Body</p>',
    )
  })

  it('matches despite the zero-width joiner a Persian title contains', () => {
    // "نقشه‌کش" is joined with a ZWNJ. Treating it as whitespace would make the
    // two copies fail to match and the duplicate would come back.
    assert.equal(
      stripDuplicatedHeading('نقشه\u200cکش<h1>نقشه\u200cکش</h1><p>Body</p>'),
      '<p>Body</p>',
    )
  })

  it('leaves a heading that disagrees with the loose text', () => {
    // Different strings mean it is not a duplicate, and dropping either one
    // would delete real content. Both copies stay.
    const html = 'Chapter One<h1>The Cartographer</h1><p>Body</p>'
    assert.equal(stripDuplicatedHeading(html), html)
  })

  it('still removes a lone heading even with no loose text at all', () => {
    assert.equal(
      stripDuplicatedHeading('<h1>Chapter One</h1><p>Body</p>'),
      '<p>Body</p>',
    )
  })

  it('only touches the very start', () => {
    const html = '<p>Intro</p><p>Title</p><h1>Title</h1>'
    assert.equal(stripDuplicatedHeading(html), html)
  })

  it('leaves a document with no heading alone', () => {
    assert.equal(stripDuplicatedHeading('<p>Body</p>'), '<p>Body</p>')
  })

  it('leaves an empty document alone', () => {
    assert.equal(stripDuplicatedHeading(''), '')
  })

  it('does not break a document that starts with a tag', () => {
    assert.equal(stripDuplicatedHeading('<p>A</p><p>B</p>'), '<p>A</p><p>B</p>')
  })
})

describe('filterChunks', () => {
  const list = rows(30)
  it('returns everything with no filters', () => {
    assert.equal(filterChunks(list, { query: '', state: 'all', flaggedOnly: false }).length, 30)
  })

  it('filters by state', () => {
    const done = filterChunks(list, { query: '', state: 'done', flaggedOnly: false })
    assert.ok(done.length > 0)
    assert.ok(done.every((row) => row.target !== ''))
  })

  it('treats an untranslated chunk as pending', () => {
    const pending = filterChunks(list, { query: '', state: 'pending', flaggedOnly: false })
    assert.ok(pending.every((row) => row.target === ''))
  })

  it('filters to flagged only', () => {
    const flagged = filterChunks(list, { query: '', state: 'flagged', flaggedOnly: false })
    assert.ok(flagged.length > 0)
    assert.ok(flagged.every((row) => row.flagged))
  })

  it('searches the source', () => {
    const found = filterChunks(list, { query: 'source text 7', state: 'all', flaggedOnly: false })
    assert.deepEqual(found.map((row) => row.id), ['chunk-7'])
  })

  it('searches the translation', () => {
    const found = filterChunks(list, { query: 'متن ترجمه 10', state: 'all', flaggedOnly: false })
    assert.deepEqual(found.map((row) => row.id), ['chunk-10'])
  })

  it('ignores case', () => {
    const found = filterChunks(list, { query: 'SOURCE TEXT 7', state: 'all', flaggedOnly: false })
    assert.equal(found.length, 1)
  })

  it('combines the filters rather than unioning them', () => {
    const combined = filterChunks(list, { query: 'source', state: 'flagged', flaggedOnly: false })
    assert.ok(combined.every((row) => row.flagged))
    assert.ok(combined.length < list.length)
  })

  it('applies flaggedOnly on top of the state filter', () => {
    const combined = filterChunks(list, { query: '', state: 'done', flaggedOnly: true })
    assert.ok(combined.every((row) => row.flagged && row.target !== ''))
  })

  it('can legitimately return nothing', () => {
    assert.deepEqual(filterChunks(list, { query: 'nothing matches this', state: 'all', flaggedOnly: false }), [])
  })

  it('tolerates surrounding whitespace in the query', () => {
    assert.equal(
      filterChunks(list, { query: '  source text 7  ', state: 'all', flaggedOnly: false }).length,
      1,
    )
  })
})
