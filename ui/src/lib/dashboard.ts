/**
 * Turning the job list into what the dashboard shows.
 *
 * ## The jobs endpoint is paginated, and that matters here
 *
 * `/api/jobs` returns `items` and `total`, and the dashboard asks for a page.
 * A time series built from one page of jobs is a series of *that page*, not of
 * the account -- and the shape would change as the page size or the sort order
 * changed, which is the kind of quiet wrongness that is hard to notice.
 *
 * So the chart is built from the page the dashboard actually has, and it says
 * so: the caption names the count it covers. When the total is larger than the
 * page, the dashboard says which jobs the chart does and does not include
 * rather than implying it is everything.
 *
 * ## Why a count per day and not the analytics aggregate
 *
 * `/api/analytics/overview` is one row with no time dimension -- `jobs`,
 * `completed_chunks`, `input_tokens`, `output_tokens`, `estimated_cost`,
 * `retries`. It is a total, so it can be a stat tile and it cannot be a chart.
 * The chart needs a dimension, and `created_at` on each job is the one that
 * exists.
 */

/** The subset of a job this module reads. Structural, so a wider payload fits. */
export interface DatedJob {
  created_at: string
  status: string
  can_resume?: boolean
}

/** Persian day initials, Sunday first, matching the week a reader starts. */
const DAY_INITIALS = ['ی', 'د', 'س', 'چ', 'پ', 'ج', 'ش'] as const

/**
 * A day bucket in the chart.
 *
 * `key` is the local date as `YYYY-MM-DD` -- used for grouping, never shown.
 * `label` is what goes under the bar, and it is one Persian character on
 * purpose: seven labels across a 393px screen leaves about 50px each.
 */
export interface DayBucket {
  key: string
  label: string
  /** How many jobs were created on this day. */
  started: number
  /** How many of those are still unfinished. */
  unfinished: number
}

/**
 * Group jobs into the last `days` calendar days, oldest first.
 *
 * Days with no jobs are present with a count of zero rather than absent. A gap
 * in a chart reads as "we do not know", and here it means "nothing happened",
 * which is a real and common answer.
 *
 * Days are bucketed in the browser's own timezone, and that is a deliberate
 * choice: the user is looking at their own day boundaries. A UTC bucket would
 * put an evening job on the next day for anyone east of Greenwich, and the
 * Persian calendar's day starts at dawn, which no timezone offset reproduces
 * anyway -- so the honest thing is the reader's own clock and a label that
 * does not claim more precision than that.
 */
export function bucketByDay(jobs: readonly DatedJob[], days = 7, now = new Date()): DayBucket[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const buckets: DayBucket[] = []
  for (let offset = days - 1; offset >= 0; offset--) {
    const day = new Date(today)
    day.setDate(today.getDate() - offset)
    buckets.push({
      key: `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(
        day.getDate(),
      ).padStart(2, '0')}`,
      // getDay() is Sunday-first, which is also the index order of DAY_INITIALS.
      label: DAY_INITIALS[day.getDay()] ?? '',
      started: 0,
      unfinished: 0,
    })
  }
  const byKey = new Map(buckets.map((bucket) => [bucket.key, bucket]))
  for (const job of jobs) {
    const stamp = new Date(job.created_at)
    if (Number.isNaN(stamp.getTime())) continue
    const key = `${stamp.getFullYear()}-${String(stamp.getMonth() + 1).padStart(2, '0')}-${String(
      stamp.getDate(),
    ).padStart(2, '0')}`
    const bucket = byKey.get(key)
    // A job older than the window has no bucket, and is not counted: the chart
    // is "the last seven days", and quietly folding a month-old job into
    // today would make the two disagree.
    if (!bucket) continue
    bucket.started += 1
    if (job.status !== 'completed') bucket.unfinished += 1
  }
  return buckets
}

/**
 * The jobs that are waiting on the reader, worst first.
 *
 * Failed before paused: a failure is a dead end and a pause is not, so the one
 * that needs a decision comes first. Within a status, newest first, because a
 * job you started this morning is the one you were thinking about.
 *
 * `limit` is applied after the sort, so the dashboard shows the most important
 * few rather than whichever happened to be on page one.
 */
export function attentionQueue<T extends DatedJob & { can_resume?: boolean }>(
  jobs: readonly T[],
  limit = 4,
): T[] {
  const rank: Record<string, number> = { failed: 0, paused: 1 }
  return [...jobs]
    .filter((job) => job.status === 'failed' || (job.status === 'paused' && job.can_resume === true))
    .sort((a, b) => {
      const byStatus = (rank[a.status] ?? 9) - (rank[b.status] ?? 9)
      if (byStatus !== 0) return byStatus
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
    .slice(0, limit)
}

/** How many jobs exist beyond the page the dashboard has. */
export function missingFromChart(total: number, shown: number): number {
  return Math.max(0, total - shown)
}

/**
 * A greeting for the dashboard hero, from the hour of day.
 *
 * Boundaries are the ordinary Persian ones: morning until noon, midday until
 * the late afternoon, evening until night. Tested at the edges because an
 * off-by-one here greets the reader wrong every single day at that hour.
 */
export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return 'صبح بخیر'
  if (hour >= 12 && hour < 17) return 'ظهر بخیر'
  if (hour >= 17 && hour < 20) return 'عصر بخیر'
  return 'شب بخیر'
}

/** Today in words, e.g. «پنجشنبه ۹ مهر ۱۴۰۵». The page shows it; the test
 *  only pins the shape, because the value changes every day. */
export function todayFa(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'full' }).format(now)
}

/**
 * The hero's one-line status: what the reader most needs to know, in words.
 *
 * Order is deliberate — stuck work outranks running work, because a running
 * job needs nothing and a failed one needs a decision. Silence also says
 * something: with no jobs at all the line points at the first step instead
 * of reporting zeros.
 */
export function heroStatus({
  running,
  stuck,
  total,
}: {
  running: number
  stuck: number
  total: number
}): string {
  const digits = new Intl.NumberFormat('fa-IR')
  if (total === 0) return 'هنوز کاری ثبت نشده — از افزودن کتاب شروع کنید.'
  if (stuck > 0 && running > 0)
    return `${digits.format(stuck)} کار نیازمند توجه و ${digits.format(running)} کار در حال ترجمه است.`
  if (stuck > 0) return `${digits.format(stuck)} کار نیازمند توجه است.`
  if (running > 0) return `${digits.format(running)} کار در حال ترجمه است.`
  return 'کاری در جریان نیست — همه‌چیز سروسامان گرفته است.'
}

export interface WeekStats {
  /** Jobs created inside the window. */
  started: number
  /** Of those, how many are completed. A cohort rate, not a global one. */
  finished: number
  /** `finished / started`, or null when nothing started: no fake 0%. */
  rate: number | null
}

/**
 * The week's pulse: what started recently and how much of it finished.
 *
 * The rate is over the week's own cohort — jobs started inside the window —
 * because that is what "this week went well" means. A global
 * completed/total would mostly measure months-old history, and there is no
 * `completed_at` on the payload to build a "finished this week" count from,
 * so this does not pretend to be one.
 */
export function weekStats(jobs: readonly DatedJob[], days = 7, now: Date = new Date()): WeekStats {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  start.setDate(start.getDate() - (days - 1))
  let started = 0
  let finished = 0
  for (const job of jobs) {
    const stamp = new Date(job.created_at)
    if (Number.isNaN(stamp.getTime()) || stamp < start || stamp > now) continue
    started += 1
    if (job.status === 'completed') finished += 1
  }
  return { started, finished, rate: started === 0 ? null : finished / started }
}
