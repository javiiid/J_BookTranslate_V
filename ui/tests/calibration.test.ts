/**
 * The calibration workshop's decisions, asserted without a DOM.
 *
 * ## What is being held here
 *
 * A workshop decides the things that are expensive to get wrong and easy to get
 * wrong quietly:
 *
 *   * **whether the profile may be sealed** — the button behind which the tone
 *     and the glossary stop being editable and the whole book is paid for. A
 *     seal that fires while a sample is unapproved or a run is in flight would
 *     lock a profile nobody read;
 *   * **which sample is active** — the id set is replaced, never appended, so
 *     "swap this one out" cannot quietly grow the sample list;
 *   * **what an unpriced figure reads as** — `null` is "unknown", and printing
 *     `$0.00` next to a start button is the one thing this project must never
 *     do (see `usd` in `lib/format.ts` for the same argument).
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { canSeal, formatCost, replaceSample, stateLabel } from '../src/lib/calibration.ts'
import type { Calibration, CalibrationSample } from '../src/lib/calibration.ts'

function sample(over: Partial<CalibrationSample> = {}): CalibrationSample {
  return {
    id: 'u1',
    chapter: 'فصل یک',
    role: 'narrative',
    source: 'متن',
    slots: [],
    result: null,
    final_verified: false,
    approved: false,
    ...over,
  }
}

function session(over: Partial<Calibration> = {}): Calibration {
  return {
    id: 'c1',
    revision: 3,
    state: 'AWAITING_USER_CALIBRATION',
    filename: 'book.epub',
    busy: null,
    job_id: null,
    approved_profile_hash: null,
    unit_count: 12,
    warnings: [],
    profile: {
      tone: 'literary',
      from_lang: 'EN',
      to_lang: 'FA',
      model: 'gpt-5.6-luna',
      final_model: 'gpt-5.6-luna',
      instructions: '',
      glossary: [],
    },
    samples: [sample({ approved: true, final_verified: true })],
    candidates: [],
    tones: [],
    budget: { sample_tokens: 40000, total_tokens: 400000, max_calls: 6, max_cost_micros: null },
    quote: {
      id: 'q1',
      plan_hash: 'h',
      pricing: 'estimated',
      input_tokens: 0,
      output_tokens: 0,
      reusable_units: 0,
      remaining_cost_low: null,
      remaining_cost_high: null,
      sample_cost: null,
      spent_cost: 0,
      reserved_cost: 0,
      spent_tokens: 0,
      sample_spent_tokens: 0,
      reserved_tokens: 0,
      sample_calls: 0,
      token_method: 'heuristic',
    },
    ...over,
  }
}

describe('canSeal', () => {
  it('permits a workshop where every sample is approved and verified', () => {
    assert.equal(canSeal(session()), true)
  })

  it('refuses while an operation is still running', () => {
    assert.equal(canSeal(session({ busy: 'op1' })), false)
  })

  it('refuses once the profile has entered the full translation', () => {
    // The server refuses edits here too (`CalibrationService.editable`), so the
    // button has to be gone for the same reason rather than for its own.
    assert.equal(canSeal(session({ job_id: 'j1' })), false)
  })

  it('refuses when no sample exists: sealing on nothing is not a cheap mistake', () => {
    assert.equal(canSeal(session({ samples: [] })), false)
  })

  it('refuses while any sample is unapproved', () => {
    const s = session({
      samples: [sample({ id: 'u1', approved: true, final_verified: true }), sample({ id: 'u2' })],
    })
    assert.equal(canSeal(s), false)
  })

  it('refuses a sample that was only drafted, never verified against the final model', () => {
    // `approved` without `final_verified` is the state a cheap preview leaves
    // behind: a reader can tick it, and then the book would be translated by a
    // model they never saw translate anything.
    assert.equal(canSeal(session({ samples: [sample({ approved: true, final_verified: false })] })), false)
  })
})

describe('replaceSample', () => {
  it('swaps one id and leaves the order alone', () => {
    const s = session({
      samples: [sample({ id: 'u1' }), sample({ id: 'u2' }), sample({ id: 'u3' })],
    })
    assert.deepEqual(replaceSample(s, 'u2', 'u9'), ['u1', 'u9', 'u3'])
  })

  it('never grows the list, which is what the server caps at three', () => {
    const s = session({ samples: [sample({ id: 'u1' }), sample({ id: 'u2' })] })
    assert.equal(replaceSample(s, 'u1', 'u8').length, 2)
  })

  it('is a no-op for an id that is not selected, rather than inserting one', () => {
    const s = session({ samples: [sample({ id: 'u1' })] })
    assert.deepEqual(replaceSample(s, 'nope', 'u8'), ['u1'])
  })

  it('collapses rather than duplicating when the replacement is already selected', () => {
    // The server rejects a duplicate set (`len(set(ids)) == len(ids)`), and the
    // dropdown hides already-selected candidates — but the helper must not
    // depend on that one filter to stay valid.
    const s = session({ samples: [sample({ id: 'u1' }), sample({ id: 'u2' })] })
    assert.deepEqual(replaceSample(s, 'u1', 'u2'), ['u2'])
  })

  it('never returns a set the server would refuse', () => {
    const s = session({ samples: [sample({ id: 'u1' }), sample({ id: 'u2' }), sample({ id: 'u3' })] })
    const out = replaceSample(s, 'u1', 'u3')
    assert.equal(new Set(out).size, out.length, `duplicate ids: ${out.join(', ')}`)
    assert.ok(out.length >= 1 && out.length <= 3)
  })
})

describe('stateLabel', () => {
  it('translates every state the server can send', () => {
    // These are the exact strings in `CalibrationService` and `runner.py`. A
    // missing one would print 24 characters of Latin beside a Persian filename.
    for (const state of [
      'AWAITING_USER_CALIBRATION',
      'CALIBRATED_AND_ESTIMATED',
      'FULL_PROCESSING',
      'COMPLETED',
      'FAILED',
      'CANCELLED',
      'PAUSED',
    ]) {
      const label = stateLabel(state)
      assert.ok(
        label !== state,
        `${state} has no Persian label, so the badge shows the raw enum`,
      )
      // 20 characters: the longest is «در حال ترجمهٔ کتاب» at 19. The badge is
      // `flex-none` beside a truncating filename, so a label that grows much
      // past this starts starving the name it sits next to.
      assert.ok(label.length <= 20, `${state} -> "${label}" is too long for a badge next to a filename`)
    }
  })

  it('shows an unfamiliar state rather than nothing', () => {
    // A new server state should read as unfamiliar, not as a blank badge.
    assert.equal(stateLabel('SOMETHING_NEW'), 'SOMETHING_NEW')
  })
})

describe('formatCost', () => {
  it('says the price is unknown rather than printing zero', () => {
    // The exact string the project forbids everywhere else: a zero beside a
    // "start" button reads as free.
    assert.equal(formatCost(null), 'نامشخص')
  })

  it('prints a known amount with Persian digits and the unit', () => {
    assert.ok(formatCost(0).includes('دلار'))
    assert.ok(formatCost(0.0831).includes('دلار'))
  })

  it('keeps five decimals, so a sub-cent estimate is not rounded to nothing', () => {
    // Sample runs on a cheap model cost fractions of a cent. At two decimals
    // the whole workshop reads as free.
    const out = formatCost(0.00237)
    assert.ok(out.includes('۰٫۰۰۲۳۷') || out.includes('0.00237'), `lost precision: ${out}`)
  })
})
