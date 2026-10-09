/**
 * The library page's decisions, asserted without a DOM.
 *
 * ## Why these are separate functions
 *
 * The page has five decisions in it that are easy to get subtly wrong and
 * impossible to see by looking at the screen: which variant a row reports on,
 * what "unfinished" counts, which book is the furthest along, what the footer
 * says on a short last page, and what a book with no chunks yet prints. All of it
 * was inline in the component, where a `className` edit could not touch it and a
 * change to how progress is computed could break every row at once.
 *
 * `node --test` has no DOM, so they are tested as plain functions and the
 * component is left holding only the rendering.
 *
 * ## The data these are written against
 *
 * The shapes come from a live `/api/library` response, not from the design. Three
 * of them are the reason most of these tests exist:
 *
 *   1. **A book can report `0 of 0` chunks.** `progress.total` is zero for a book
 *      that was uploaded and never chunked, while its own status is `completed`.
 *      Dividing by it produces `NaN`, and `NaN` as a bar width is an invisible
 *      bar next to a caption reading "0 of 0 chunks" -- which is the whole
 *      failure this module is shaped around.
 *   2. **Titles are raw filenames.** `overthesevensea`, `flex test`,
 *      `040061b0658b 06a220543f6e flex test`. There are no spaces to break on and
 *      no capitals to take an initial from, which is why a cover falls back to
 *      the file extension.
 *   3. **11 of 31 books were `failed` and 4 were `available`** -- so a fifth of
 *      the library is unfinished in one way or the other, and neither of those two
 *      states is a "running" one.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  LIBRARY_TABS,
  activeVariant,
  chunkProgress,
  coverInitials,
  furthestProgress,
  lastReadable,
  libraryStats,
  pageCount,
  pageRange,
  percentOf,
  progressLadder,
  readableVariant,
  recentActivity,
} from '../src/lib/library.ts'
import type { LibraryBook, LibraryVariant } from '../src/lib/api.ts'

function variant(over: Partial<LibraryVariant> = {}): LibraryVariant {
  return {
    id: 1,
    job_id: 'job-1',
    path: 'C:/output/book.epub',
    kind: 'translated',
    size_bytes: 1024,
    created_at: '2026-09-28T12:00:00+00:00',
    archived: 0,
    book_id: 1,
    display_name: 'book.epub',
    extension: 'epub',
    mime_type: 'application/epub+zip',
    language: 'FA',
    checksum: '',
    is_readable: 1,
    page_count: 0,
    chapter_count: 0,
    last_opened_at: null,
    last_read_location: null,
    status: 'completed',
    progress: { completed: 60, total: 60 },
    error: null,
    download: '/downloads/job-1',
    reader: '/reader/job-1',
    ...over,
  }
}

function book(over: Partial<LibraryBook> = {}): LibraryBook {
  return {
    id: 1,
    title: 'overthesevensea',
    author: '',
    cover_path: null,
    created_at: '2026-09-28T12:00:00+00:00',
    updated_at: '2026-09-28T12:00:00+00:00',
    status: 'completed',
    variants: [variant()],
    size_bytes: 4096,
    translated: true,
    readable: true,
    ...over,
  }
}

describe('which variant a row reports on', () => {
  it('prefers the translation, whatever order the endpoint sent', () => {
    const original = variant({ id: 1, kind: 'original' })
    const translated = variant({ id: 2, kind: 'translated' })
    // The endpoint orders translation-first today. The page must not depend on
    // that staying true, so the answer here is by name and not by position.
    const subject = book({ variants: [original, translated] })
    assert.equal(activeVariant(subject)?.id, 2)
  })

  it('falls back to the original when there is no translation', () => {
    const original = variant({ id: 1, kind: 'original' })
    assert.equal(activeVariant(book({ variants: [original] }))?.id, 1)
  })

  it('is undefined for a book with no variants at all', () => {
    assert.equal(activeVariant(book({ variants: [] })), undefined)
  })
})

describe('progress as a percentage', () => {
  it('is null when there is no denominator, and not zero', () => {
    // The uploaded-never-chunked book: `0 of 0`. Reporting 0% would claim the
    // work measured a floor of nothing; reporting NaN would draw a bar of no
    // width next to a caption. `null` is the only answer that is neither.
    assert.equal(percentOf(variant({ progress: { completed: 0, total: 0 } })), null)
  })

  it('rounds, so the bar and its caption describe the same thing', () => {
    // 95/268 is 35.45%. A bar at 35.45% under a caption saying 35 is a bar whose
    // label does not describe it.
    assert.equal(percentOf(variant({ progress: { completed: 95, total: 268 } })), 35)
  })

  it('is 100 for a finished variant', () => {
    assert.equal(percentOf(variant({ progress: { completed: 60, total: 60 } })), 100)
  })

  it('is 0 for a variant that has measured its floor', () => {
    assert.equal(percentOf(variant({ progress: { completed: 0, total: 6 } })), 0)
  })

  it('clamps rather than exceeding 100 on a bad payload', () => {
    assert.equal(percentOf(variant({ progress: { completed: 70, total: 60 } })), 100)
  })

  it('reads nothing when the variant is missing', () => {
    assert.equal(percentOf(undefined), null)
  })
})

describe('the heading line under a row', () => {
  it('is null with no denominator, so no "0 of 0" is ever printed', () => {
    assert.equal(chunkProgress(variant({ progress: { completed: 0, total: 0 } })), null)
    assert.equal(chunkProgress(undefined), null)
  })

  it('is the two numbers when there is one', () => {
    assert.deepEqual(
      chunkProgress(variant({ progress: { completed: 95, total: 268 } })),
      { completed: 95, total: 268 },
    )
  })
})

describe('the four figures', () => {
  it('counts unfinished as the complement of finished', () => {
    // The endpoint resolves a book to `completed` as soon as any variant
    // completed, so total-completed is exactly the set its other statuses
    // partition. Adding the other statuses up separately would be the same
    // number arrived at four times, three of them able to disagree.
    const stats = libraryStats({ total: 31, running: 0, completed: 16, failed: 11 })
    assert.equal(stats.unfinished, 15)
  })

  it('never reports a negative unfinished count', () => {
    assert.equal(libraryStats({ total: 4, running: 0, completed: 9, failed: 0 }).unfinished, 0)
  })

  it('keeps failed separate from unfinished', () => {
    // 11 of the 15 unfinished books broke; the other 4 were never queued. A
    // page that showed 15 above a `خطادار` tab that opened 11 books would be
    // wrong on screen, so the two are separate figures and both are named.
    const stats = libraryStats({ total: 31, running: 0, completed: 16, failed: 11 })
    assert.equal(stats.failed, 11)
    assert.equal(stats.unfinished - stats.failed, 4)
  })

  it('has no share for an empty library, rather than a share of zero', () => {
    // "0% of the library is translated" on a library with nothing in it is a
    // claim about a set that does not exist.
    assert.equal(libraryStats({ total: 0, running: 0, completed: 0, failed: 0 }).completedShare, null)
  })

  it('rounds the share', () => {
    assert.equal(
      libraryStats({ total: 31, running: 0, completed: 16, failed: 11 }).completedShare,
      52,
    )
  })
})

describe('the filter tabs', () => {
  it('has four, in the order of what to do about it', () => {
    assert.deepEqual(
      LIBRARY_TABS.map((tab) => tab.key),
      ['', 'running', 'failed', 'completed'],
    )
  })

  it('draws every tab count from a figure the endpoint also filters on', () => {
    // This is the assertion that keeps a tab honest. A tab whose number came
    // from a bucket the endpoint cannot filter on would show one figure and
    // open a list of another -- which is the mismatch that made "ناتمام ۱۵" sit
    // above a list of 11.
    const filters = LIBRARY_TABS.filter((tab) => tab.key !== '').map((tab) => tab.key)
    for (const tab of LIBRARY_TABS) {
      // Either the tab has no filter (all books) or its count key names the same
      // bucket its filter asks the server for.
      if (tab.key === '') continue
      assert.equal(tab.count, tab.key, `${tab.label} filters on "${tab.key}" but counts "${tab.count}"`)
      assert.ok(filters.includes(tab.key))
    }
  })

  it('does not offer a filter the endpoint does not have', () => {
    for (const tab of LIBRARY_TABS) {
      if (tab.key === '') continue
      assert.ok(
        ['completed', 'running', 'failed', 'available'].includes(tab.key),
        `${tab.key} is not a status the endpoint can filter on`,
      )
    }
  })

  it('names the failed tab for what it holds', () => {
    // `available` books -- uploaded, never queued -- are not in this bucket.
    // Calling the tab "unfinished" would be the lie; it says "خطادار".
    const tab = LIBRARY_TABS.find((entry) => entry.key === 'failed')
    assert.equal(tab?.label, 'خطادار')
  })
})

describe('the furthest-along book', () => {
  const unfinished = (id: number, completed: number, total: number, updated: string) =>
    book({
      id,
      status: 'failed',
      updated_at: updated,
      variants: [
        variant({ id, progress: { completed, total }, status: 'failed' }),
      ],
    })

  it('is the one with the highest percent, not the one with the most chunks', () => {
    // 53/60 is 88%; 95/268 is 35%. Comparing raw chunk counts would have named
    // the 95-chunk book, which is nowhere near being finished and is exactly
    // what the card is asking you not to pick.
    const subject = furthestProgress([
      unfinished(1, 95, 268, '2026-10-01T15:25:00+00:00'),
      unfinished(2, 53, 60, '2026-09-27T11:28:00+00:00'),
    ])
    assert.equal(subject?.book.id, 2)
    assert.equal(subject?.percent, 88)
  })

  it('never names a finished book', () => {
    // A book at 100% belongs on the "continue reading" card. At the top of a
    // card about half-done books it would be an answer to a different question.
    assert.equal(furthestProgress([book({ id: 9, status: 'completed' })]), null)
  })

  it('breaks a tie on the more recently touched book', () => {
    const subject = furthestProgress([
      unfinished(1, 5, 10, '2026-09-01T00:00:00+00:00'),
      unfinished(2, 5, 10, '2026-09-20T00:00:00+00:00'),
    ])
    assert.equal(subject?.book.id, 2)
  })

  it('is null when nothing is half done', () => {
    assert.equal(furthestProgress([]), null)
    assert.equal(
      furthestProgress([book({ status: 'failed', variants: [variant({ progress: { completed: 0, total: 0 } })] })]),
      null,
    )
  })
})

describe('the histogram behind that card', () => {
  const unfinished = (id: number, completed: number, total: number) =>
    book({
      id,
      status: 'failed',
      variants: [variant({ id, progress: { completed, total }, status: 'failed' })],
    })

  it('is the same books as the card, best first', () => {
    // The tallest bar has to be the book named beside it. If the two were
    // computed differently the chart would contradict its own caption.
    const books = [
      unfinished(1, 95, 268),
      unfinished(2, 53, 60),
      unfinished(3, 13, 17),
    ]
    const ladder = progressLadder(books, 5)
    assert.deepEqual(ladder.map((row) => row.book.id), [2, 3, 1])
    assert.equal(furthestProgress(books)?.book.id, ladder[0]?.book.id)
  })

  it('holds five bars, because the card is drawn with five', () => {
    const many = Array.from({ length: 9 }, (_, index) => unfinished(index, index + 1, 20))
    assert.equal(progressLadder(many, 5).length, 5)
  })

  it('asks for zero bars without throwing', () => {
    assert.deepEqual(progressLadder([unfinished(1, 5, 10)], 0), [])
  })

  it('leaves out finished books', () => {
    assert.equal(progressLadder([book({ status: 'completed' })], 5).length, 0)
  })
})

describe('the last readable book', () => {
  it('needs a reader path, not just the readable flag', () => {
    // The flag and the path are set by two different conditions in the
    // endpoint, and only the path is what the link needs. A failed book has
    // translated chunks but nothing to open -- so its variant carries an empty
    // `reader`, which is exactly what the endpoint sends for anything that is
    // not a translated EPUB with a job behind it.
    const failed = book({
      id: 3,
      status: 'failed',
      readable: true,
      variants: [variant({ status: 'failed', reader: '' })],
    })
    assert.equal(readableVariant(failed), undefined)
    assert.equal(lastReadable([failed]), null)
  })

  it('is the most recently updated one that can be opened', () => {
    const older = book({ id: 1, updated_at: '2026-09-20T00:00:00+00:00' })
    const newer = book({ id: 2, updated_at: '2026-10-02T00:00:00+00:00' })
    assert.equal(lastReadable([older, newer])?.book.id, 2)
  })

  it('is null on a library with nothing finished in it', () => {
    // An empty `reader` rather than an absent key: `library_summary` only sets
    // the field on a translated EPUB that has a job, and the page treats an
    // empty path as "nothing to open" rather than as a link to nowhere.
    const pending = book({
      status: 'available',
      readable: false,
      variants: [variant({ kind: 'original', status: 'available', reader: '' })],
    })
    assert.equal(lastReadable([pending]), null)
  })
})

describe('the last activity line', () => {
  it('is the newest timestamp, compared as a string', () => {
    // Every timestamp the endpoint emits is UTC with a +00:00 offset, so ISO-8601
    // sorts correctly as text -- and a malformed value cannot become a Date and
    // produce NaN in the middle of a heading.
    const newest = recentActivity([
      book({ id: 1, updated_at: '2026-09-20T00:00:00+00:00' }),
      book({ id: 2, updated_at: '2026-10-02T09:00:00+00:00' }),
      book({ id: 3, updated_at: '2026-09-28T00:00:00+00:00' }),
    ])
    assert.equal(newest, '2026-10-02T09:00:00+00:00')
  })

  it('is null for an empty library', () => {
    assert.equal(recentActivity([]), null)
  })
})

describe('the footer', () => {
  it('counts from one on the first page', () => {
    assert.deepEqual(pageRange(1, 12, 31), { from: 1, to: 12 })
  })

  it('does not run past the end on a short last page', () => {
    // 31 books at 12 a page is three pages, and the last one holds seven. Saying
    // "13 to 24" there would be a range that does not exist.
    assert.deepEqual(pageRange(3, 12, 31), { from: 25, to: 31 })
  })

  it('is all zeroes rather than "1 to 0" when there is nothing', () => {
    assert.deepEqual(pageRange(1, 12, 0), { from: 0, to: 0 })
  })

  it('has one page for an empty library, so a pager always has a page one', () => {
    assert.equal(pageCount(0, 12), 1)
  })

  it('has one page when everything fits', () => {
    assert.equal(pageCount(12, 12), 1)
  })

  it('rounds a partial page up', () => {
    assert.equal(pageCount(13, 12), 2)
  })

  it('does not divide by a zero limit', () => {
    assert.equal(pageCount(31, 0), 1)
  })
})

describe('the cover that is not a cover', () => {
  it('uses the file extension, because the titles are raw filenames', () => {
    // `flex test` and `040061b0658b 06a220543f6e flex test` are what this
    // library actually holds. An initial of the title is an "f" on half the rows,
    // while EP against PD is at least something a reader can tell apart.
    assert.equal(coverInitials(book({ title: 'flex test' })), 'EP')
  })

  it('follows the variant, so an original and its translation share a cover', () => {
    const original = book({
      variants: [variant({ kind: 'original', extension: 'pdf' }), variant({ kind: 'translated', extension: 'epub' })],
    })
    assert.equal(coverInitials(original), 'EP')
  })

  it('falls back to a word of the title when there is no extension', () => {
    const subject = book({
      title: 'The Overstory',
      variants: [variant({ extension: '' })],
    })
    assert.equal(coverInitials(subject), 'TH')
  })

  it('does not throw on a book with no title and no variant', () => {
    assert.equal(typeof coverInitials(book({ title: '', variants: [] })), 'string')
  })
})