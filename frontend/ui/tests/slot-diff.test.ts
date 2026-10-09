import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { diffSummary, wordDiff } from '../src/lib/slotDiff.ts'

describe('wordDiff', () => {
  it('returns nothing for two empty strings', () => {
    assert.deepEqual(wordDiff('', ''), [])
  })

  it('marks identical text as all same', () => {
    const parts = wordDiff('معماری تمیز است', 'معماری تمیز است')
    assert.ok(parts.length > 0)
    assert.ok(parts.every((p) => p.kind === 'same'))
    assert.equal(parts.map((p) => p.text).join(''), 'معماری تمیز است')
  })

  it('finds an added word without touching the rest', () => {
    const parts = wordDiff('معماری تمیز', 'معماری خیلی تمیز')
    const adds = parts.filter((p) => p.kind === 'add')
    assert.equal(adds.length, 1)
    assert.ok((adds[0]?.text ?? '').includes('خیلی'))
    assert.equal(diffSummary(parts).added, 1)
    assert.equal(diffSummary(parts).removed, 0)
  })

  it('finds a removed word and keeps half-spaces inside words', () => {
    const parts = wordDiff('کتاب‌های خوب', 'کتاب‌های')
    const dels = parts.filter((p) => p.kind === 'del')
    assert.equal(dels.length, 1)
    assert.ok((dels[0]?.text ?? '').includes('خوب'))
    // ZWNJ inside a word must not split it into a diff of its own.
    assert.ok(!parts.some((p) => p.text === '‌'))
  })

  it('round-trips: dels rebuild the base, adds+sames rebuild the edit', () => {
    const base = 'نگهداشت حالت در حافظه محلی'
    const edited = 'نگهداشت وضعیت در حافظه محلی مرورگر'
    const parts = wordDiff(base, edited)
    const rebuiltBase = parts
      .filter((p) => p.kind !== 'add')
      .map((p) => p.text)
      .join('')
    const rebuiltEdited = parts
      .filter((p) => p.kind !== 'del')
      .map((p) => p.text)
      .join('')
    assert.equal(rebuiltBase, base)
    assert.equal(rebuiltEdited, edited)
  })

  it('falls back to whole-block verdicts on pathological inputs', () => {
    const huge = Array.from({ length: 700 }, (_, i) => `w${i}`).join(' ')
    const parts = wordDiff(huge, huge + ' extra')
    assert.ok(parts.every((p) => p.kind === 'add' || p.kind === 'del'))
  })
})
