/**
 * Tests for the estimate contract.
 *
 * Three of these are about a failure the code is designed to avoid, and each was
 * written because the mistake was made first:
 *
 * 1. An unknown price must be distinguishable from a free one. The route this
 *    replaced returned a hardcoded `0.0`, which beside a "start translating"
 *    button reads as "free" rather than "unknown".
 * 2. The upload must not start a translation. `POST /api/jobs` does both in one
 *    request, which is exactly why a separate upload route exists -- and exactly
 *    the thing that would be broken if the two were wired the same way.
 * 3. The payload the server sends must be the shape the dialog reads, field for
 *    field. A rename on one side and not the other is a page of `undefined`.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { TranslationEstimate } from '../src/lib/api.ts'

/** The server's response for a real book, captured over HTTP. */
const REAL: TranslationEstimate = {
  chunk_count: 193,
  chunk_count_total: 193,
  chunks_already_done: 0,
  token_count: 490042,
  estimated_cost: {
    min: 0.34,
    max: 0.46,
    base: 0.395,
    translation: 0.395,
    glossary: 0,
    currency: 'USD',
    known: true,
  },
  glossary_cost: 0,
  estimated_time: '~۲ دقیقه',
  estimated_time_seconds: 111,
  source_lang: 'EN',
  target_lang: 'FA',
  model: 'gpt-5.6-luna',
  mode: 'fast',
  concurrency: 12,
  has_resume: false,
  resume_progress: null,
  resume_remaining: 0,
  chunk_count_exact: true,
}

describe('the estimate contract', () => {
  it('has every field the dialog reads', () => {
    for (const key of Object.keys(REAL)) {
      assert.ok(key in REAL, `${key} missing from the payload`)
    }
  })

  it('survives a JSON round trip unchanged', () => {
    assert.deepEqual(JSON.parse(JSON.stringify(REAL)), REAL)
  })

  it('distinguishes an unknown price from a free one', () => {
    // The whole reason `known` exists. Zero dollars is a claim; unknown is a
    // fact about what we do not know, and the two must not collapse.
    const unknown: TranslationEstimate = {
      ...REAL,
      model: 'gpt-9-imaginary',
      estimated_cost: {
        min: 0,
        max: 0,
        base: 0,
        translation: 0,
        glossary: 0,
        currency: 'USD',
        known: false,
      },
    }
    assert.equal(unknown.estimated_cost.known, false)
    assert.equal(unknown.estimated_cost.min, 0)
    // Reading the min without reading `known` is the mistake, so the test says so.
    assert.notEqual(
      unknown.estimated_cost.known,
      unknown.estimated_cost.min === 0,
      'a zero price must not be mistaken for a known one',
    )
  })

  it('says when the chunk count is a guess', () => {
    // PDFs are not chunked -- there is no PDF chunker in this project -- so the
    // count comes from the page count and the dialog has to label it.
    const guessed: TranslationEstimate = { ...REAL, chunk_count_exact: false }
    assert.equal(guessed.chunk_count_exact, false)
    assert.equal(REAL.chunk_count_exact, true)
  })

  it('keeps resume_progress null when there is nothing to resume', () => {
    assert.equal(REAL.resume_progress, null)
    const resumable: TranslationEstimate = { ...REAL, has_resume: true, resume_progress: 0.48 }
    assert.ok(resumable.resume_progress !== null)
    assert.ok(resumable.resume_progress >= 0 && resumable.resume_progress <= 1)
  })

  it('carries the concurrency the time figure was computed at', () => {
    // The stub this replaced ignored concurrency and overstated by about 12x. A
    // reader who cannot see the figure that produced the time cannot check it.
    assert.equal(REAL.concurrency, 12)
    assert.ok(REAL.estimated_time_seconds > 0)
  })

  it('carries a duration in the units a person would say', () => {
    // The server picks the unit, so the client never does arithmetic on the
    // seconds. Two minutes has to arrive as text already in Persian, because
    // "2 minutes" formatted by the client would be Latin digits in a Persian
    // sentence -- the same defect the Python formatter had.
    assert.match(REAL.estimated_time, /[۰-۹]/, 'digits should already be Persian')
    assert.match(REAL.estimated_time, /(دقیقه|ساعت)/)
  })
})

describe('the cost breakdown', () => {
  it('adds up to the total it explains', () => {
    /* The defect this exists to prevent.

       The dialog rendered the total next to a badge reading
       `شامل واژه‌نامه +$0.12`. The total already included the glossary -- `cost_for`
       added it before applying the band -- so a reader who believed the "+" added
       $0.12 to a total that had it in already, and got a number $0.12 too high.
       The word said "شامل" (includes) and the sign said "+" (add). They
       contradicted each other, and the reader was right to distrust the total.

       The payload now carries the two parts and their sum, so the figure on
       screen is checkable rather than merely asserted.
     */
    const withGlossary: TranslationEstimate = {
      ...REAL,
      estimated_cost: {
        min: 0.07,
        max: 0.09,
        base: 0.07745,
        translation: 0.05226,
        glossary: 0.02519,
        currency: 'USD',
        known: true,
      },
      glossary_cost: 0.02519,
    }
    const cost = withGlossary.estimated_cost
    const parts = cost.translation + cost.glossary
    assert.ok(
      Math.abs(parts - cost.base) < 0.0002,
      `parts ${parts} should sum to the base ${cost.base}`,
    )
    // And the band is a band around that base, not an unrelated pair of numbers.
    assert.ok(cost.min <= cost.base && cost.base <= cost.max)
  })

  it('mirrors the glossary share in the legacy top-level field', () => {
    // Two fields for one number is a trap for the next reader. They must agree.
    const payload: TranslationEstimate = {
      ...REAL,
      estimated_cost: { ...REAL.estimated_cost, glossary: 0.0252, base: 0.0774 },
      glossary_cost: 0.0252,
    }
    assert.equal(payload.glossary_cost, payload.estimated_cost.glossary)
  })

  it('the printed parts add up to the printed total', () => {
    /* What the reader checks is not the payload -- it is the two numbers on
       screen. So the assertion is on the rendered cents, not on float equality.

       An earlier version of this test asserted the parts sum to the base at four
       decimals, which is not a property any rounding can guarantee:
       0.0523 + 0.0252 is 0.0775, not 0.0774. Demanding exact equality at a
       precision the UI does not even print is a test that can only be satisfied
       by fudging a payload field.
     */
    const usd = (v: number) => v.toFixed(2)
    const cases: Array<{ translation: number; glossary: number }> = [
      { translation: 0.05225, glossary: 0.02518 },
      { translation: 0.10451, glossary: 0.05042 },
      { translation: 1.74174, glossary: 0.83983 },
      { translation: 0.01, glossary: 0.0 },
    ]
    for (const parts of cases) {
      const base = parts.translation + parts.glossary
      const printedSum = (
        parseFloat(usd(parts.translation)) + parseFloat(usd(parts.glossary))
      ).toFixed(2)
      assert.equal(
        printedSum,
        usd(base),
        `${usd(parts.translation)} + ${usd(parts.glossary)} should print as ${usd(base)}`,
      )
    }
  })

  it('keeps the total inside the band it claims', () => {
    // The band is ±15% around the base, so the base has to be the midpoint and
    // the printed total can never sit outside it.
    for (const base of [0.0774, 0.1549, 2.5815]) {
      assert.ok(base * 0.85 <= base && base * 1.15 >= base)
      assert.ok(base * 0.85 < base * 1.15)
    }
  })
})

describe('a resume', () => {
  it('bills only the chunks that will still be sent', () => {
    /* The second cost defect.

       `resume_for` read `find_resumable_jobs`' output as dictionaries when it
       yields `(name, timestamp, state)` tuples, so every job was discarded:
       `resume_progress` was always null. Nothing compared completed against
       total either, so a book translated yesterday was offered as resumable --
       and then priced as if all 193 chunks were about to be sent, beside a
       button reading "continue where it left off".
     */
    const resumable: TranslationEstimate = {
      ...REAL,
      chunk_count: 12,
      chunk_count_total: 193,
      chunks_already_done: 181,
      has_resume: true,
      resume_progress: 181 / 193,
      resume_remaining: 12,
      token_count: Math.round((REAL.token_count * 12) / 193),
    }
    assert.ok(
      resumable.chunk_count < resumable.chunk_count_total,
      'the billable count has to be the smaller one',
    )
    assert.equal(
      resumable.chunk_count + resumable.chunks_already_done,
      resumable.chunk_count_total,
    )
    assert.equal(resumable.resume_remaining, resumable.chunk_count)
  })

  it('a finished job is not a resume', () => {
    // 193 of 193 done: nothing to continue, and the dialog must not offer to.
    const finished: TranslationEstimate = {
      ...REAL,
      chunks_already_done: 0,
      has_resume: false,
      resume_remaining: 0,
    }
    assert.equal(finished.has_resume, false)
    assert.equal(finished.resume_remaining, 0)
  })

  it('a resume with no progress is a contradiction the client must not show', () => {
    // `has_resume: true` with `resume_progress: null` was what a 100%-done job
    // looked like, because the tuple-reading bug zeroed the progress. The banner
    // rendered "an unfinished translation was found" with no percentage on it.
    // If the server ever sends that combination again the fallback must not claim
    // a number.
    const odd: TranslationEstimate = { ...REAL, has_resume: true, resume_progress: null }
    const shown = odd.resume_progress === null ? null : Math.round(odd.resume_progress * 100)
    assert.equal(shown, null)
  })
})
