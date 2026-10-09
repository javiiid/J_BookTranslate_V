/**
 * Turning the library payload into what the library page shows.
 *
 * ## Why this is a `.ts` and not part of the page
 *
 * Everything here is a decision that is easy to get subtly wrong and impossible
 * to see by looking at the screen: which variant a row reports on, what
 * "unfinished" means, which book counts as the furthest along, and what the
 * footer says when a page is the last one and shorter than the page size. All of
 * it was inline in the component, where a `className` edit could not touch it
 * and a date-format edit could break it silently.
 *
 * `node --test` has no DOM, so the decisions are exported as plain functions and
 * `tests/library.test.ts` drives them directly. The component keeps the
 * rendering and nothing else.
 *
 * ## The one rule everything else follows from
 *
 * **A book is finished when the backend says so, and progress is the
 * translation's own numbers.** The endpoint computes a book's `status` as
 * "completed if any variant completed", and that same rule is what `unfinished`
 * inverts here. The alternative -- asking whether `completed === total` -- looks
 * equivalent and is not: on the data this was written against there is a book
 * whose only variant reports `0 of 0` chunks and whose status is `completed`,
 * and dividing by a total of zero is where a page starts printing `NaN`.
 *
 * ## Why the counts come from separate requests
 *
 * `/api/library` pages its results and returns `total` for whatever filter is
 * active. A count per filter therefore costs one request each, and the page
 * makes them rather than fetching every book to count them in JavaScript:
 * `library_summary` loads the whole table on every call anyway, so a "fetch it
 * all and count locally" version would be both slower and silently wrong past
 * the 100-row ceiling the endpoint clamps `limit` to.
 *
 * The two spotlight cards are the exception, because they need a *book*, not a
 * count. They read a single wide page and say so below.
 */

import type { LibraryBook, LibraryStatusFilter, LibraryVariant } from './api'

/**
 * The variant a row reports on.
 *
 * The translation if there is one, else the first variant. A book with only its
 * uploaded original still has progress worth showing -- "not started yet" is a
 * state a reader needs to see, and it is carried by the variant's `0 of N`, not
 * by an absence.
 *
 * The backend orders variants translation-first (`CASE kind WHEN 'translated'`)
 * so `variants[0]` would usually be right anyway; asking for the translation by
 * name means the answer does not depend on that ordering staying as it is.
 */
export function activeVariant(book: LibraryBook): LibraryVariant | undefined {
  const variants = book.variants ?? []
  return variants.find((variant) => variant.kind === 'translated') ?? variants[0]
}

/**
 * How far along a variant is, as a whole percent.
 *
 * `null` when there is no denominator, and that is a real state rather than an
 * edge case: a book that has been uploaded but never chunked reports `0 of 0`.
 * Returning `null` lets the caller print an em dash; returning `0` would claim
 * the work has measured a floor of nothing and is exactly the kind of number
 * that reads as "nothing is wrong here".
 *
 * Rounded, because a bar drawn at 87.4% and a caption saying 87% is a bar whose
 * label does not describe it.
 */
export function percentOf(variant: LibraryVariant | undefined): number | null {
  if (!variant) return null
  const total = variant.progress?.total ?? 0
  if (total <= 0) return null
  const completed = variant.progress?.completed ?? 0
  return Math.min(100, Math.max(0, Math.round((completed * 100) / total)))
}

/** The heading line under a row: `۶۰ از ۲۶۸ بخش`, or an em dash with no numbers. */
export function chunkProgress(variant: LibraryVariant | undefined): {
  completed: number
  total: number
} | null {
  if (!variant) return null
  const total = variant.progress?.total ?? 0
  if (total <= 0) return null
  return { completed: variant.progress?.completed ?? 0, total }
}

/** Whether a book has a translation the reader can open in the browser. */
export function readableVariant(book: LibraryBook): LibraryVariant | undefined {
  return (book.variants ?? []).find(
    (variant) => typeof variant.reader === 'string' && variant.reader.length > 0,
  )
}

/**
 * The four counters along the top of the page.
 *
 * `total` and `completed` are the endpoint's own `total` for the unfiltered and
 * `status=completed` requests, so they are exact at any library size.
 *
 * `unfinished` is `total - completed` rather than a fourth request: the endpoint
 * resolves a book's status to `completed` as soon as *any* variant completed, so
 * `total - completed` is precisely the set the endpoint's other statuses
 * partition -- counting them separately and adding them up would be the same
 * number arrived at four times, three of them able to disagree with the fourth.
 */
export interface LibraryStats {
  total: number
  running: number
  completed: number
  /** The endpoint's `failed` bucket: work that broke rather than never started. */
  failed: number
  /** Neither running nor finished. Includes `failed` and `available`. */
  unfinished: number
  /** Finished books, as a share of the library, or `null` when it is empty. */
  completedShare: number | null
}

export function libraryStats(input: {
  total: number
  running: number
  completed: number
  failed: number
}): LibraryStats {
  const { total, running, completed, failed } = input
  return {
    total,
    running,
    completed,
    failed,
    unfinished: Math.max(0, total - completed),
    completedShare: total > 0 ? Math.round((completed * 100) / total) : null,
  }
}

/**
 * One tab in the filter row.
 *
 * `key` is the backend's `status` parameter; the empty string is "no filter",
 * which is a value the endpoint already understands by omission.
 */
export interface LibraryFilterTab {
  key: LibraryStatusFilter | ''
  label: string
  /** Which counter in `LibraryStats` fills the tab's number. */
  count: keyof Pick<LibraryStats, 'total' | 'running' | 'completed' | 'failed'>
}

/**
 * The four tabs, in reading order: everything, then what is moving, then what
 * broke, then what is done.
 *
 * Every one of these is a bucket the endpoint can filter on, and every one of
 * these numbers comes from the endpoint's own `total` for that filter. An
 * earlier version had a fifth state -- "unfinished", meaning `failed` plus the
 * books that were never queued -- and it was a mismatch that showed: the tab
 * said 15 while the list it opened held 11, because the endpoint's `failed`
 * filter cannot express "or never started". The compromise was to widen the
 * bucket in JavaScript, which made the tab honest and the list a lie.
 *
 * So the tab is `failed`, labelled as such, and the wider "unfinished" idea
 * survives where it is true: the `جلد ناتمام` figure above it, which is a
 * count and not a filter, and is computed as `total - completed`.
 *
 * `available` books -- uploaded, never queued -- are reachable through "همه" and
 * through the row's own badge. They get no tab, because a tab that hides three
 * quarters of the library's non-finished books is a worse default than not
 * offering it.
 */
export const LIBRARY_TABS: readonly LibraryFilterTab[] = [
  { key: '', label: 'همه کتاب‌ها', count: 'total' },
  { key: 'running', label: 'در حال ترجمه', count: 'running' },
  { key: 'failed', label: 'خطادار', count: 'failed' },
  { key: 'completed', label: 'تکمیل‌شده', count: 'completed' },
]

/** A book picked for one of the two spotlight cards. */
export interface Spotlight {
  book: LibraryBook
  variant: LibraryVariant
  percent: number
}

/**
 * The unfinished book that got furthest.
 *
 * "Furthest" is the highest percentage among books that are not finished, so
 * the card answers "which of my half-done books is closest to being worth
 * finishing" -- which is the question that card exists to answer. A book at 88%
 * is more use there than the one at 100%, which is finished and belongs on the
 * other card.
 *
 * Ties go to the more recently updated book, because between two books at the
 * same percentage the one touched last is the one in mind.
 *
 * `null` when there is no unfinished book with a denominator at all, which is
 * what an empty or all-finished library looks like.
 */
export function furthestProgress(books: readonly LibraryBook[]): Spotlight | null {
  let best: Spotlight | null = null
  for (const book of books) {
    if (book.status === 'completed') continue
    const variant = activeVariant(book)
    const percent = percentOf(variant)
    if (percent === null || percent >= 100) continue
    if (!variant) continue
    if (
      best === null ||
      percent > best.percent ||
      (percent === best.percent && book.updated_at > best.book.updated_at)
    ) {
      best = { book, variant, percent }
    }
  }
  return best
}

/**
 * The unfinished books that got furthest, best first, capped at `count`.
 *
 * This is the data behind the spotlight card's small histogram. It is the same
 * ordering as `furthestProgress` over a set of books rather than one, so the
 * tallest bar in the chart is always the book named in the card beside it --
 * a chart whose peak is some other book than the one the heading claims is a
 * chart that contradicts its own caption.
 *
 * Books at 100% are excluded for the same reason `furthestProgress` excludes
 * them: a finished book is not a candidate for "furthest along without being
 * finished", and drawing it at full height would put a completed book at the
 * top of a card about incomplete ones.
 */
export function progressLadder(
  books: readonly LibraryBook[],
  count = 5,
): Spotlight[] {
  const rows: Spotlight[] = []
  for (const book of books) {
    if (book.status === 'completed') continue
    const variant = activeVariant(book)
    const percent = percentOf(variant)
    if (percent === null || percent >= 100 || !variant) continue
    rows.push({ book, variant, percent })
  }
  rows.sort(
    (a, b) =>
      b.percent - a.percent ||
      (b.book.updated_at > a.book.updated_at ? 1 : b.book.updated_at < a.book.updated_at ? -1 : 0),
  )
  return rows.slice(0, Math.max(0, count))
}

/**
 * The most recently updated book that can actually be opened.
 *
 * Requires a `reader` path on the variant rather than the book's `readable`
 * flag alone, because the flag and the path are set by two different conditions
 * in `library_summary` and only the path is what the link needs. A failed book
 * has translated chunks but no reader -- there is nothing to open -- so it is
 * skipped instead of being linked and then found to be empty.
 */
export function lastReadable(books: readonly LibraryBook[]): Spotlight | null {
  let best: Spotlight | null = null
  for (const book of books) {
    const variant = readableVariant(book)
    if (!variant) continue
    if (best === null || book.updated_at > best.book.updated_at) {
      const percent = percentOf(variant)
      if (percent === null) continue
      best = { book, variant, percent }
    }
  }
  return best
}

/**
 * The newest `updated_at` in a set of books, or `null`.
 *
 * ISO-8601 with an offset sorts correctly as a string, and every timestamp the
 * endpoint emits is UTC with a `+00:00` offset, so no `Date` is constructed --
 * and a malformed value cannot produce `NaN` in the middle of a heading.
 */
export function recentActivity(books: readonly LibraryBook[]): string | null {
  let newest: string | null = null
  for (const book of books) {
    if (newest === null || book.updated_at > newest) newest = book.updated_at
  }
  return newest
}

/** The span a page covers, for the footer's "showing 1 to 12 of 31". */
export function pageRange(page: number, limit: number, total: number): {
  from: number
  to: number
} {
  if (total <= 0 || limit <= 0) return { from: 0, to: 0 }
  const from = (page - 1) * limit + 1
  return { from: Math.min(from, total), to: Math.min(page * limit, total) }
}

/** How many pages a result set has. Never zero, so a pager always has a page 1. */
export function pageCount(total: number, limit: number): number {
  if (limit <= 0) return 1
  return Math.max(1, Math.ceil(total / limit))
}

/**
 * Two letters for a cover that has no image.
 *
 * `cover_path` carries a real extracted cover for books shelved through the
 * current backend (`app/library/covers.py` reads it from the EPUB package or
 * renders the PDF's first page). This fallback remains for books whose file
 * has no usable image. Falling back to the extension rather than the title
 * is deliberate: titles here are raw filenames (`overthesevensea.epub`), so
 * an initial of the title is an `o` on thirty-one rows and tells the reader
 * nothing, while `EP` against a `PD` is at least a distinction they can act
 * on.
 *
 * A word in the title is preferred when there is one, so a library of properly
 * titled books shows two of its own letters instead.
 */
export function coverInitials(book: LibraryBook): string {
  const variant = activeVariant(book)
  const extension = variant?.extension?.trim()
  if (extension) return extension.slice(0, 2).toUpperCase()
  const word = book.title.trim().split(/\s+/).find((part) => /[\p{L}]/u.test(part))
  return (word ?? book.title)
    .slice(0, 2)
    // Uppercased like the extension branch above: the two letters sit in the
    // same box in the same face, and a tile reading `th` next to tiles reading
    // `EP` looks like two different kinds of thing rather than one fallback.
    .toUpperCase()
}

/** The status of a book's active variant, falling back to the book's own. */
export function rowStatus(book: LibraryBook): string {
  return activeVariant(book)?.status ?? book.status
}