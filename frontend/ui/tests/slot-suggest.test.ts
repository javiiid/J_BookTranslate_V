import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { normalizeTerm, slotSuggestions } from '../src/lib/slotSuggest.ts'
import type { CalibrationTerm } from '../src/lib/calibration.ts'

function term(over: Partial<CalibrationTerm> = {}): CalibrationTerm {
  return {
    id: 't1',
    source_term: 'clean architecture',
    target_term: 'معماری تمیز',
    kind: 'term',
    notes: '',
    approved: true,
    locked: false,
    evidence_id: '',
    ...over,
  }
}

describe('normalizeTerm', () => {
  it('casefolds latin and folds compatibility characters the way the backend does', () => {
    assert.equal(normalizeTerm('Clean Architecture'), 'clean architecture')
    // Fullwidth compatibility characters fold under NFKC.
    assert.equal(normalizeTerm('ｃｌｅａｎ'), 'clean')
    // Arabic Yeh (U+064A) and Persian Yeh (U+06CC) have no compatibility
    // decomposition, so neither NFKC here nor the backend folds them:
    // a term must be entered with the same Yeh it appears with.
    assert.notEqual(normalizeTerm('علي'), normalizeTerm('علی'))
  })
})

describe('slotSuggestions', () => {
  it('suggests an approved term found in the slot', () => {
    const out = slotSuggestions('This book is about clean architecture patterns.', [term()])
    assert.equal(out.length, 1)
    assert.equal(out[0]?.target_term, 'معماری تمیز')
  })

  it('ignores unapproved terms and terms with an empty equivalent', () => {
    const out = slotSuggestions('clean architecture', [
      term({ id: 'a', approved: false }),
      term({ id: 'b', target_term: '  ' }),
    ])
    assert.deepEqual(out, [])
  })

  it('prefers longer (more specific) source terms and caps at three', () => {
    const glossary = [
      term({ id: 'short', source_term: 'architecture', target_term: 'معماری' }),
      term({ id: 'long', source_term: 'clean architecture', target_term: 'معماری تمیز' }),
      term({ id: 't3', source_term: 'book', target_term: 'کتاب' }),
      term({ id: 't4', source_term: 'patterns', target_term: 'الگوها' }),
      term({ id: 't5', source_term: 'about', target_term: 'درباره' }),
    ]
    const out = slotSuggestions('This book is about clean architecture patterns.', glossary)
    assert.equal(out.length, 3)
    assert.equal(out[0]?.id, 'long')
  })

  it('stays silent when nothing matches', () => {
    assert.deepEqual(slotSuggestions('nothing relevant here', [term()]), [])
    assert.deepEqual(slotSuggestions('', [term()]), [])
  })
})
