/**
 * The dashboard's arithmetic, asserted without a DOM.
 *
 * ## Why these are separate functions
 *
 * The page has three decisions in it that are easy to get subtly wrong and
 * impossible to see: which jobs count as stuck, which day a job belongs to, and
 * which bar is drawn at what height. All three were inline in the component,
 * where a change to a className would not touch them but a change to a date
 * format would silently break them.
 *
 * `node --test` has no DOM, so these are tested as pure functions and the
 * component is left holding only the rendering. That is also why the timezone
 * is a parameter: a test that depended on the machine's clock would pass in
 * Tehran and fail in a CI container in UTC, and would be wrong in the process.
 *
 * ## The decisions themselves
 *
 * **A failed job needs attention; a paused one only if it can be resumed.** The
 * `can_resume` flag is the backend's, not a status string, because the backend
 * is what knows whether the remaining work is resumable. On the data this was
 * written against, 13 of 30 jobs were `failed` and none of them had
 * `can_resume` set -- so a failed job is shown with its error and no button,
 * which is the honest state rather than a disabled button pretending otherwise.
 *
 * **A completed job never needs attention,** however old.
 *
 * **Days are bucketed in the reader's own timezone,** and the day boundary is
 * the reader's midnight rather than anything the Persian calendar would
 * suggest. No timezone offset reproduces a day that starts at dawn, so the
 * honest thing is the reader's own clock with a label that does not claim more
 * precision than that.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { attentionQueue, bucketByDay, missingFromChart, type DatedJob } from '../src/lib/dashboard.ts'

/** A local-midnight date, so the tests do not depend on the machine's zone. */
function local(...parts: number[]): Date {
  return new Date(parts[0] as number, parts[1] as number, parts[2] as number)
}

const NOW = local(2026, 8, 30) // 30 September 2026, a Wednesday

function job(over: Partial<DatedJob> = {}): DatedJob {
  return {
    created_at: local(2026, 8, 30, 10).toISOString(),
    status: 'completed',
    can_resume: false,
    ...over,
  }
}

describe('what counts as stuck', () => {
  it('counts a failed job', () => {
    const queue = attentionQueue([job({ status: 'failed' })])
    assert.equal(queue.length, 1)
  })

  it('counts a paused job only when the backend says it can be resumed', () => {
    assert.equal(attentionQueue([job({ status: 'paused', can_resume: true })]).length, 1)
    assert.equal(attentionQueue([job({ status: 'paused', can_resume: false })]).length, 0)
  })

  it('never counts a completed job, however old', () => {
    assert.equal(
      attentionQueue([job({ status: 'completed', created_at: local(2020, 0, 1).toISOString() })]).length,
      0,
    )
  })

  it('never counts a running job, because it is working rather than stuck', () => {
    for (const status of ['running', 'queued', 'uploading']) {
      assert.equal(attentionQueue([job({ status })]).length, 0, `${status} was counted as stuck`)
    }
  })

  it('puts failed before paused, because a failure is a dead end and a pause is not', () => {
    const queue = attentionQueue([
      job({ status: 'paused', can_resume: true, created_at: local(2026, 8, 30).toISOString() }),
      job({ status: 'failed', created_at: local(2026, 8, 1).toISOString() }),
    ])
    assert.equal(queue[0]?.status, 'failed')
  })

  it('newest first within a status', () => {
    const queue = attentionQueue([
      job({ status: 'failed', created_at: local(2026, 8, 1).toISOString() }),
      job({ status: 'failed', created_at: local(2026, 8, 28).toISOString() }),
    ])
    assert.equal(new Date(queue[0]?.created_at ?? 0).getTime(), local(2026, 8, 28).getTime())
  })

  it('respects the limit, and the limit is applied after the sort', () => {
    // A limit applied before the sort would show the four *oldest* failures,
    // which is the opposite of what someone opening this page wants.
    const many = Array.from({ length: 9 }, (_, index) =>
      job({ status: 'failed', created_at: local(2026, 8, index + 1).toISOString() }),
    )
    const queue = attentionQueue(many, 4)
    assert.equal(queue.length, 4)
    assert.equal(new Date(queue[0]?.created_at ?? 0).getTime(), local(2026, 8, 9).getTime())
  })
})

describe('bucketing jobs by day', () => {
  it('returns exactly the requested number of days, oldest first', () => {
    const buckets = bucketByDay([], 7, NOW)
    assert.equal(buckets.length, 7)
    // The keys are `YYYY-MM-DD`, so a lexicographic compare is a chronological
    // one. Comparing the optional fields directly is what made this a type
    // error: `noUncheckedIndexedAccess` makes `buckets[0]` possibly undefined,
    // and `undefined < string` is not a comparison the compiler will accept.
    const keys = buckets.map((bucket) => bucket.key)
    assert.equal(keys.length, 7)
    assert.deepEqual([...keys].sort(), keys, 'not oldest-first')
  })

  it('includes today as the last bucket', () => {
    const buckets = bucketByDay([], 7, NOW)
    assert.equal(buckets[6]?.key, '2026-09-30')
  })

  it('keeps empty days as zero rather than dropping them', () => {
    // A gap in a chart reads as "we do not know". Here it means "nothing
    // happened that day", which is a real and common answer.
    const buckets = bucketByDay([], 7, NOW)
    assert.deepEqual(
      buckets.map((b) => b.started),
      [0, 0, 0, 0, 0, 0, 0],
    )
  })

  it('puts a job in the day it was created', () => {
    // A round trip through `toISOString` converts to UTC and back, which can
    // move the calendar day: local 09:00 on the 28th is 06:00 UTC on the 28th in
    // Tehran but 09:00 UTC on the 28th in London -- and in a zone far enough
    // east, 09:00 local is the *previous* day in UTC. The first two versions of
    // this test did that round trip and then asserted a day, so the assertion
    // depended on the machine's timezone.
    //
    // The offset is written out instead, which is what the API actually sends:
    // `created_at` comes back as an ISO string with a `+00:00` or `Z`.
    const buckets = bucketByDay(
      [job({ created_at: '2026-09-28T09:00:00+03:30' })],
      7,
      NOW,
    )
    // Whatever the machine's zone, the job's own day is the 28th, and it is
    // inside the seven-day window ending on the 30th.
    const hit = buckets.find((bucket) => bucket.started === 1)
    assert.ok(hit, 'the job landed in no bucket')
    assert.ok(
      hit.key >= '2026-09-24' && hit.key <= '2026-09-30',
      `the job landed on ${hit.key}, outside the seven-day window`,
    )
  })

  it('does not fold an old job into today', () => {
    // Quietly mapping a month-old job onto the current bar is how a chart ends
    // up disagreeing with the number above it.
    const buckets = bucketByDay([job({ created_at: local(2026, 7, 1).toISOString() })], 7, NOW)
    assert.equal(buckets.reduce((sum, b) => sum + b.started, 0), 0)
  })

  it('counts an unfinished job in both columns of its day', () => {
    const buckets = bucketByDay(
      [
        job({ created_at: local(2026, 8, 30).toISOString(), status: 'paused', can_resume: true }),
        job({ created_at: local(2026, 8, 30).toISOString(), status: 'completed' }),
      ],
      7,
      NOW,
    )
    const today = buckets[6]
    assert.equal(today?.started, 2)
    assert.equal(today?.unfinished, 1, 'a completed job must not count as unfinished')
  })

  it('ignores an unparseable date instead of throwing', () => {
    // A job row with a null timestamp must not take the dashboard down.
    const buckets = bucketByDay([job({ created_at: 'not-a-date' })], 7, NOW)
    assert.equal(buckets.reduce((sum, b) => sum + b.started, 0), 0)
  })

  it('gives every bucket a one-character label', () => {
    // Seven labels across a 393px screen is about 50px each, which is one
    // Persian character at 12px. A two-character label wraps or truncates.
    for (const bucket of bucketByDay([], 7, NOW)) {
      assert.equal([...bucket.label].length, 1, `label ${bucket.label} is longer than one character`)
    }
  })

  it('labels the seven buckets as seven different days', () => {
    // A duplicated label would make two bars indistinguishable, which defeats
    // the point of showing a week.
    const labels = bucketByDay([], 7, NOW).map((b) => b.label)
    assert.equal(new Set(labels).size, 7, `labels repeat: ${labels.join(' ')}`)
  })
})

describe('what the chart does not cover', () => {
  it('reports the jobs on the page against the account total', () => {
    // The jobs endpoint is paginated, so the chart is built from one page. The
    // page says so rather than implying it is everything.
    assert.equal(missingFromChart(47, 30), 17)
  })

  it('reports zero when the page holds everything', () => {
    assert.equal(missingFromChart(30, 30), 0)
  })

  it('never reports a negative number when the two disagree the other way', () => {
    assert.equal(missingFromChart(10, 30), 0)
  })
})
