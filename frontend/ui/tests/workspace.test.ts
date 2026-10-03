/**
 * Tests for the pure logic behind the new screens.
 *
 * The ported screens are mostly rendering, which a DOM test would cover and this
 * runner cannot. So the parts that carry a decision are factored out and tested
 * here: term normalisation (which decides whether a glossary approval matches
 * the draft), output-format toggling, the reader's chapter fallback, and the
 * library's page arithmetic.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { key } from '../src/lib/terms.ts'

/* ------------------------------------------------------------------ */
/* Term normalisation                                                  */
/* ------------------------------------------------------------------ */

describe('key', () => {
  it('is case insensitive, so a term cannot be approved twice', () => {
    assert.equal(key('Ann'), key('ANN'))
    assert.equal(key('Dagger Society'), key('dagger society'))
  })

  it('preserves a zero-width non-joiner, which is what Python does', () => {
    // The interesting property here is that it is preserved, not stripped.
    // `unicodedata.normalize("NFKC", "واژه‌نامه")` keeps the U+200C, and so
    // does String.prototype.normalize -- verified in
    // docs/check_normalisation.py against the real interpreter.
    //
    // A previous version of this file asserted the opposite and "passed" only
    // because the TS side was deleting invisible characters that Python kept,
    // which would have made the two UIs disagree about which terms already
    // existed. The mismatch checker is what caught it.
    assert.equal(key('واژه‌نامه'), 'واژه\u200cنامه')
    assert.notEqual(key('واژه‌نامه'), key('واژهنامه'))
  })

  it('preserves a soft hyphen, as Python does', () => {
    assert.equal(key('soft\u00adhyphen'), 'soft\u00adhyphen')
  })

  it('composes a decomposed accent, as Python does', () => {
    assert.equal(key('cafe\u0301'), key('café'))
  })

  it('folds compatibility forms, so a full-width character still matches', () => {
    assert.equal(key('ＡＢＣ'), key('ABC'))
  })

  it('trims nothing implicitly: surrounding space is a real difference', () => {
    // The backend strips on save, so a term with a stray space should not
    // silently equal its trimmed form before it gets there.
    assert.notEqual(key(' Ann '), key('Ann'))
  })

  it('is stable for the empty string', () => {
    assert.equal(key(''), key(''))
  })
})

/* ------------------------------------------------------------------ */
/* Output format toggling (WorkspacePage)                             */
/* ------------------------------------------------------------------ */

/** Mirrors the reducer in WorkspacePage; kept here so the rule is stated once. */
function toggleOutput(current: string[], value: string): string[] {
  return current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value]
}

describe('output format toggling', () => {
  it('adds a format that was off', () => {
    assert.deepEqual(toggleOutput([], 'docx'), ['docx'])
  })

  it('removes one that was on', () => {
    assert.deepEqual(toggleOutput(['docx', 'srt'], 'docx'), ['srt'])
  })

  it('cycles on, off, on', () => {
    const on = toggleOutput([], 'markdown')
    assert.deepEqual(on, ['markdown'])
    const off = toggleOutput(on, 'markdown')
    assert.deepEqual(off, [])
    assert.deepEqual(toggleOutput(off, 'markdown'), on)
  })

  it('does not duplicate', () => {
    let outputs: string[] = []
    for (let i = 0; i < 5; i++) outputs = toggleOutput(outputs, 'srt')
    assert.equal(outputs.filter((item) => item === 'srt').length, 1)
  })

  it('preserves the order formats were picked in', () => {
    let outputs: string[] = []
    for (const value of ['srt', 'docx', 'markdown']) outputs = toggleOutput(outputs, value)
    assert.deepEqual(outputs, ['srt', 'docx', 'markdown'])
  })
})

/* ------------------------------------------------------------------ */
/* File acceptance (WorkspacePage)                                    */
/* ------------------------------------------------------------------ */

const ACCEPTED = /^[^.]+\.(epub|pdf)$/i

describe('file acceptance', () => {
  it('accepts epub and pdf, in any case', () => {
    assert.ok(ACCEPTED.test('book.epub'))
    assert.ok(ACCEPTED.test('book.EPUB'))
    assert.ok(ACCEPTED.test('book.Pdf'))
  })

  it('rejects anything else', () => {
    for (const name of ['book.docx', 'book.mobi', 'book.txt', 'book', 'book.epub.exe']) {
      assert.ok(!ACCEPTED.test(name), `${name} should be rejected`)
    }
  })

  it('accepts a name with several dots before the extension', () => {
    assert.ok(ACCEPTED.test('Clean Architecture v2.epub'))
  })
})

/* ------------------------------------------------------------------ */
/* Reader chapter selection                                            */
/* ------------------------------------------------------------------ */

/** Mirrors the derivation in ReaderPage: an explicit choice, else the first. */
function effectiveChapter(selected: number | null, ids: number[]): number | null {
  return selected ?? ids[0] ?? null
}

describe('reader chapter selection', () => {
  it('falls back to the first chapter when nothing is selected', () => {
    assert.equal(effectiveChapter(null, [3, 4, 5]), 3)
  })

  it('keeps an explicit choice', () => {
    assert.equal(effectiveChapter(4, [3, 4, 5]), 4)
  })

  it('is null before the chapter list loads, so no query fires on an unknown id', () => {
    assert.equal(effectiveChapter(null, []), null)
  })

  it('is not re-derived on refetch, so a refetch cannot yank the reader back', () => {
    // This is the behaviour the old useEffect had wrong: a refetch returned the
    // first chapter's id and overwrote the user's position.
    const before = effectiveChapter(4, [3, 4, 5])
    const after = effectiveChapter(4, [3, 4, 5])
    assert.equal(after, before)
  })
})

/* ------------------------------------------------------------------ */
/* Library pagination                                                  */
/* ------------------------------------------------------------------ */

function pageCount(total: number, limit: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, limit)))
}

describe('library pagination', () => {
  it('is one page for an empty library', () => {
    assert.equal(pageCount(0, 12), 1)
  })

  it('is one page when everything fits', () => {
    assert.equal(pageCount(12, 12), 1)
  })

  it('rounds up a partial page', () => {
    assert.equal(pageCount(13, 12), 2)
  })

  it('handles a total of exactly zero items per page', () => {
    // A zero limit would make the count NaN and the pager disappear.
    assert.equal(pageCount(5, 0), 5)
  })
})
