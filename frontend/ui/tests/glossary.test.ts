/**
 * Reader glossary highlighting decisions, asserted without a DOM.
 *
 * `prepareGlossTerms` re-pins the server's contract (non-empty sides,
 * longest source first, capped) instead of trusting the wire order.
 * `findTermAt` pins the match rule: case-insensitive on the original text,
 * NFKC fallback with the hit mapped back, so marks wrap on-screen casing.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  GLOSS_TARGET_SLICE,
  MAX_GLOSS_MARKS,
  MAX_GLOSS_TERMS,
  findTermAt,
  prepareGlossTerms,
  textFor,
  tipFor,
} from '../src/lib/glossary.ts'

const term = (source_term: string, target_term: string) => ({ source_term, target_term })

describe('preparing glossary terms', () => {
  it('drops entries with an empty side, which would match everywhere', () => {
    assert.deepEqual(prepareGlossTerms([term('', 'x'), term('y', ''), term(' ', '  ')]), [])
    assert.deepEqual(prepareGlossTerms(null), [])
    assert.deepEqual(prepareGlossTerms(undefined), [])
  })

  it('sorts longest source first, so a phrase beats its own prefix', () => {
    const terms = prepareGlossTerms([
      term('قرارداد', 'contract'),
      term('قرارداد کار', 'employment contract'),
      term('کار', 'work'),
    ])
    assert.deepEqual(terms.map((entry) => entry.source), ['قرارداد کار', 'قرارداد', 'کار'])
  })

  it('caps at forty and slices the tip side at sixty', () => {
    const many = Array.from({ length: 60 }, (_, index) => term(`term${index}`, 'x'.repeat(100)))
    const terms = prepareGlossTerms(many)
    assert.equal(terms.length, MAX_GLOSS_TERMS)
    assert.ok(terms.every((entry) => entry.target.length <= GLOSS_TARGET_SLICE))
  })

  it('keeps the zero-width non-joiner inside Persian terms', () => {
    // Stripping U+200C would merge distinct words; the Python side keeps it
    // and so does the port.
    const word = 'می\u200cخوانم'
    assert.deepEqual(prepareGlossTerms([term(word, 'reads')]), [{ source: word, target: 'reads' }])
  })
})

describe('finding a term in text', () => {
  it('finds the exact occurrence', () => {
    assert.deepEqual(findTermAt('the contract binds', 'contract'), { index: 4, length: 8 })
  })

  it('matches case-insensitively but reports the on-screen span', () => {
    assert.deepEqual(findTermAt('The Contract binds', 'contract'), { index: 4, length: 8 })
  })

  it('respects the start offset', () => {
    assert.deepEqual(findTermAt('work and more work', 'work', 5), { index: 14, length: 4 })
    assert.equal(findTermAt('work and more', 'work', 99), null)
  })

  it('never matches an empty needle', () => {
    assert.equal(findTermAt('anything', ''), null)
  })

  it('falls back to NFKC forms and maps the hit back', () => {
    // Fullwidth ABC is three units; NFKC folds it to two... no: to 'ABC'.
    const hit = findTermAt('see ＡＢＣ now', 'ABC')
    assert.ok(hit !== null)
    assert.equal('see ＡＢＣ now'.slice(hit!.index, hit!.index + hit!.length), 'ＡＢＣ')
  })

  it('maps a ligature hit back to the on-screen span', () => {
    // U+FB01 'ﬁ' is one unit on screen, two ('fi') normalized: matching
    // 'file' must wrap 'ﬁle' (three units), not just the ligature.
    const text = 'a ﬁle'
    const hit = findTermAt(text, 'file')
    assert.deepEqual(hit, { index: 2, length: 3 })
    assert.equal(text.slice(hit!.index, hit!.index + hit!.length), 'ﬁle')
  })
})

describe('side-aware tips', () => {
  const entry = { source: 'قرارداد', target: 'contract' }

  it('matches the side the node is in and tips the other', () => {
    assert.equal(textFor(entry, 'source'), 'قرارداد')
    assert.equal(textFor(entry, 'target'), 'contract')
    assert.equal(tipFor(entry, 'source'), 'contract')
    assert.equal(tipFor(entry, 'target'), 'قرارداد')
  })

  it('caps the chapter at two hundred marks', () => {
    assert.equal(MAX_GLOSS_MARKS, 200)
  })
})
