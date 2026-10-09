import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { canEnterStep, nextIncompleteStep, reviewChecks, roleLabelFor, toneDescription, toneLabel, wizardStepLabel } from '../src/lib/calibrationSteps.ts'
import type { Calibration } from '../src/lib/calibration.ts'
import { setLocale } from '../src/lib/locale.ts'

function session(over: Partial<Calibration> = {}): Calibration {
  const sample = (id: string, s: object = {}) => ({
    id,
    chapter: 'ch',
    role: 'narrative',
    source: 'text',
    slots: [],
    result: { translations: [], plain: 'x', model: 'm', origin: 'model' as const, reused: false },
    final_verified: true,
    approved: true,
    ...s,
  })
  return {
    id: 'c1',
    revision: 1,
    state: 'AWAITING_USER_CALIBRATION',
    filename: 'book.epub',
    busy: null,
    job_id: null,
    approved_profile_hash: null,
    unit_count: 4,
    warnings: [],
    profile: { tone: 'literary', from_lang: 'EN', to_lang: 'FA', model: 'a', final_model: 'a', instructions: '', glossary: [] },
    samples: [sample('u1'), sample('u2')],
    candidates: [],
    tones: [],
    budget: { sample_tokens: 40000, total_tokens: 400000, max_calls: 6, max_cost_micros: null },
    quote: {
      id: 'q1', plan_hash: 'h', pricing: 'estimated', input_tokens: 0, output_tokens: 0,
      reusable_units: 0, remaining_cost_low: null, remaining_cost_high: null, sample_cost: null,
      spent_cost: 0, reserved_cost: 0, spent_tokens: 0, sample_spent_tokens: 0,
      reserved_tokens: 0, sample_calls: 0, token_method: 'heuristic',
    },
    ...over,
  } as Calibration
}

describe('canEnterStep', () => {
  it('allows every step on a normal session: only the seal is gated, not the view', () => {
    const s = session()
    for (const step of [0, 1, 2, 3] as const) {
      assert.equal(canEnterStep(s, step), true)
    }
  })

  it('still allows review when samples are unverified: the checklist explains instead of blocking', () => {
    const s = session({ samples: [{ id: 'u1', chapter: 'c', role: 'n', source: 't', slots: [], result: null, final_verified: false, approved: false }] as never })
    assert.equal(canEnterStep(s, 3), true)
    assert.equal(reviewChecks(s).every((c) => c.ok), false)
  })

  it('starts at step 0 without a session', () => {
    assert.equal(canEnterStep(null, 0), true)
    assert.equal(canEnterStep(undefined, 1), false)
  })
})

describe('reviewChecks', () => {
  it('passes all three on a seal-ready workshop', () => {
    assert.deepEqual(reviewChecks(session()).map((c) => c.ok), [true, true, true])
  })

  it('names the missing approval instead of a bare disabled button', () => {
    const s = session({ samples: [{ id: 'u1', chapter: 'c', role: 'n', source: 't', slots: [], result: null, final_verified: true, approved: false }] as never })
    const labels = reviewChecks(s).map((c) => c.label).join(' ')
    assert.ok(labels.length > 10)
    assert.equal(reviewChecks(s)[0]?.ok, false)
  })

  it('reports a running operation as not sealable', () => {
    const s = session({ busy: 'op1' })
    assert.equal(reviewChecks(s)[2]?.ok, false)
  })
})

describe('nextIncompleteStep', () => {
  it('points at tone when a sample has no result yet', () => {
    const s = session({ samples: [{ id: 'u1', chapter: 'c', role: 'n', source: 't', slots: [], result: null, final_verified: false, approved: false }] as never })
    assert.equal(nextIncompleteStep(s), 0)
  })

  it('points at review when everything is approved and verified', () => {
    assert.equal(nextIncompleteStep(session()), 3)
  })
})

describe('localized display text', () => {
  it('translates tones by stable id and falls back to the server words', () => {
    setLocale('fa')
    assert.equal(toneLabel('literary', 'SERVER'), 'ادبی و تمثیلی')
    setLocale('en')
    try {
      assert.equal(toneLabel('literary', 'SERVER'), 'Literary & figurative')
      assert.ok(toneDescription('modern', 'SERVER').includes('Persian'))
      assert.equal(toneLabel('future-tone', 'SERVER'), 'SERVER')
      assert.equal(roleLabelFor('dialogue'), 'Dialogue')
      assert.equal(wizardStepLabel(0), 'Translation tone')
    } finally {
      setLocale('fa')
    }
  })
})
