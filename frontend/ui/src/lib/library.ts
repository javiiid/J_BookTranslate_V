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
  /** Neither running nor finished. Includes `failed` and `available`. */
  unfinished: number
  /** Finished books, as a share of the library, or `null` when it is empty. */
  completedShare: number | null
}

export function libraryStats(input: {
  total: number
  running: number
  completed: number
}): LibraryStats {
  const { total, running, completed } = input
  return {
    total,
    running,
    completed,
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
  count: keyof Pick<LibraryStats, 'total' | 'running' | 'completed' | 'unfinished'>
}

/**
 * The four tabs, in reading order: everything, then what is moving, then what is
 * stuck, then what is done.
 *
 * The order is the order of "what do I do about it", so the numbers read as a
 * funnel. `unfinished` is sent as the endpoint's own `failed` filter and then
 * widened -- see `matchesFilter` -- because a book that was never started
 * (`available`) is just as unfinished as one that broke halfway.
 */
export const LIBRARY_TABS: readonly LibraryFilterTab[] = [
  { key: '', label: 'همه کتاب‌ها', count: 'total' },
  { key: 'running', label: 'در حال ترجمه', count: 'running' },
  { key: 'failed', label: 'ناتمام', count: 'unfinished' },
  { key: 'completed', label: 'تکمیل‌شده', count: 'completed' },
]

/**
 * Whether a book belongs in a tab, for the tabs the endpoint cannot express.
 *
 * The endpoint's `status=failed` matches a book whose status is `failed`, and
 * nothing else. But the tab is labelled "unfinished", and a book sitting
 * `available` -- uploaded, never queued -- is the *most* unfinished thing in the
 * library. So this widens the bucket locally.
 *
 * It exists at all because the list is server-filtered and paged while the tab's
 * count is whole-library: without it, "ناتمام ۱۵" would sit above a list holding
 * only the 11 that failed. The honest fix is a backend filter; until then this is
 * the smaller of the two mismatches, and the page prefers the server's list.
 */
export function matchesFilter(book: LibraryBook, key: LibraryStatusFilter | ''): boolean {
  if (key === '') return true
  if (key === 'failed') return book.status !== 'completed'
  return book.status === key
}

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
 * `cover_path` is null for every book in the database this was written against
 * -- the column is populated by the Python page's upload path and nothing has
 * written to it yet -- so a design with a cover column needs a cover that is not
 * a cover. Falling back to the extension rather than the title is deliberate:
 * titles here are raw filenames (`overthesevensea.epub`), so an initial of the
 * title is an `o` on thirty-one rows and tells the reader nothing, while `EP`
 * against a `PD` is at least a distinction they can act on.
 *
 * A word in the title is preferred when there is one, so a library of properly
 * titled books shows two of its own letters instead.
 */
export function coverInitials(book: LibraryBook): string {
  const variant = activeVariant(book)
  const extension = variant?.extension?.trim()
  if (extension) return extension.slice(0, 2).toUpperCase()
  const word = book.title.trim().split(/\s+/).find((part) => /[\p{L}]/u.test(part))
  return (word ?? book.title).slice(0, 2)
}

/** The status of a book's active variant, falling back to the book's own. */
export function rowStatus(book: LibraryBook): string {
  return activeVariant(book)?.status ?? book.status
}