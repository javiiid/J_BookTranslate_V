import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { LibraryBook, LibraryShelf, LibraryStatusFilter } from '@/lib/api'
import { fa, faAgo, faBytes, faDate, badgeClass, statusLabel } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { StringKey } from '@/i18n/fa.ts'
import {
  LIBRARY_TABS,
  activeVariant,
  bookShelf,
  bookTags,
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
} from '@/lib/library'
import { NavIcon } from '@/components/NavIcon'
import './library.css'

/**
 * The library.
 *
 * ## What the page is for
 *
 * It used to be a list: a heading, a search box and one card per book, each card
 * repeating its own title, badges and progress bar. Every number a reader wants
 * -- how many books are here, how many are unfinished, which one is closest to
 * being worth finishing, what was I last reading -- had to be counted by hand
 * from the cards.
 *
 * It is now those numbers first and the list second, in this order:
 *
 *   0. **The heading.** One band, so the page's one title is not competing with
 *      the rail, a status pill and four figures at the same level.
 *   1. **Four figures.** Total, running, finished, unfinished. The last two are
 *      complements of the first, and shown as two because "how many of my books
 *      are done" and "how many are not" are different questions.
 *   2. **Two answers.** Which half-done book got furthest, and what was last
 *      read. Neither is a statistic -- each is a book and a way in.
 *   3. **The list**, filtered and paged server-side, with the filter row showing
 *      each bucket's whole-library count before you choose it.
 *
 * ## Where the numbers come from, and why it costs four requests
 *
 * `/api/library` pages its results and returns `total` for the active filter, so
 * a count per bucket costs one request each. The alternative -- one wide fetch
 * counted in JavaScript -- is both slower (`library_summary` loads the whole
 * table per call regardless) and wrong past the 100-row ceiling the endpoint
 * clamps `limit` to.
 *
 * The one place that does take a wide page is the two spotlight cards, because
 * they need a book rather than a count. That is `SPOTLIGHT_LIMIT` and it is
 * commented where it is used.
 *
 * ## What it will not do
 *
 * Books without a usable image keep the generated extension tile: the backend
 * extracts real covers where it can (`app/library/covers.py`), and the tile
 * below becomes an `<img>` whenever `cover_path` is set.
 *
 * There is no sorting control either, though the design had one. The endpoint
 * takes `q`, `status` and `type` and returns `updated_at DESC`; a sort menu
 * would be four options of which only one does anything. Until the endpoint
 * sorts, the honest list is "most recently touched first".
 *
 * And "unfinished" is the one filter this page widens locally rather than asking
 * the server for -- see `matchesFilter` for why, and for what it costs.
 */

const PAGE_SIZE = 12

/**
 * How many books the two spotlight cards look at.
 *
 * The endpoint clamps `limit` to 100 and orders by `updated_at DESC`, so this is
 * "the hundred most recently touched books", which is the right window for "what
 * was I last reading" and a good-enough one for "which is furthest along". A
 * library past a hundred books that has an abandoned book at 90% outside the
 * window would have its card name the wrong book; that is the trade, and it is
 * stated rather than hidden. The four figures do not have this problem, because
 * they come from `total`.
 */
const SPOTLIGHT_LIMIT = 100

/**
 * The one status the shared labels do not know, as a dictionary key.
 *
 * `statusLabel` and `badgeClass` in `format.ts` carry the seven job statuses,
 * and this page uses those rather than its own copies -- they are the same words
 * the Python pages use, and a second table here is how the two drift apart.
 *
 * A book can also be `available`, which is not a job status: the file was
 * uploaded and never queued, so the endpoint reports it as its own thing. It is
 * named through the dictionary so both languages print a word rather than the
 * raw Latin `available`; the seven stay named once, in one place, for
 * everything else.
 */
const bookStatusLabel = (t: (key: StringKey) => string, status: string): string =>
  status === 'available' ? t('library.status.available') : statusLabel(status)

/**
 * A variant kind, as a dictionary key. Unknown future kinds fall back to the
 * raw value from the API rather than a blank badge.
 */
const KIND_KEY: Record<string, StringKey> = {
  original: 'library.kind.original',
  translated: 'library.kind.translated',
  main: 'library.kind.main',
}

const kindLabel = (t: (key: StringKey) => string, kind: string): string => {
  const key = KIND_KEY[kind]
  return key ? t(key) : kind
}

/**
 * A reading shelf, as a dictionary key. Same shape as `KIND_KEY` for the same
 * reason: an unknown future shelf renders its raw value rather than nothing.
 * This is reading state, not translation state — see `bookShelf`.
 */
const SHELF_KEY: Record<string, StringKey> = {
  want: 'library.shelf.want',
  reading: 'library.shelf.reading',
  finished: 'library.shelf.finished',
}

const shelfLabel = (t: (key: StringKey) => string, shelf: string): string => {
  const key = SHELF_KEY[shelf]
  return key ? t(key) : shelf
}

/** A file format, as the badge on the cover and in the row's meta line. */
function extensionOf(book: LibraryBook): string {
  const extension = activeVariant(book)?.extension
  return (extension ?? 'file').toUpperCase()
}

/**
 * A cover tile.
 *
 * An `<img>` when the book has a cover, and otherwise two letters on the
 * primary wash. The two letters are the file extension rather than the title's
 * initial, because the titles in this library are raw filenames -- `flex test`,
 * `040061b0658b 06a220543f6e flex test` -- so an initial of the title is a `f`
 * on half the rows and tells a reader nothing they can act on.
 */
function BookCover({ book }: { book: LibraryBook }) {
  if (book.cover_path) {
    return (
      <span className="lib-cover">
        <img className="lib-cover-image" src={book.cover_path} alt="" loading="lazy" />
      </span>
    )
  }
  return (
    <span className="lib-cover" aria-hidden="true">
      {coverInitials(book)}
    </span>
  )
}

/** A four-figure summary. `tone` is a token name, passed as a whole. */
function Tile({
  icon,
  label,
  value,
  hint,
  bar,
}: {
  icon: 'library' | 'monitor' | 'reader' | 'add'
  label: string
  value: string
  hint: string
  /** 0-100 to draw a bar, or `null` for a tile whose number is not a share. */
  bar: number | null
}) {
  return (
    <div className="lib-tile">
      <span className="lib-tile-icon" aria-hidden="true">
        <NavIcon name={icon} size={20} />
      </span>
      <span className="lib-tile-label">{label}</span>
      <strong className="lib-tile-value">{value}</strong>
      {bar === null ? null : (
        <span className="lib-tile-bar">
          {/* `div` and not `span`: `.progress-track` sets a height, and a height
              on an inline box does nothing, so a span would draw a bar of zero
              height with a full-width background on top of it. */}
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${bar}%` }} />
          </div>
        </span>
      )}
      <span className="lib-tile-hint">{hint}</span>
    </div>
  )
}

/**
 * The per-book menu.
 *
 * A `<details>` element, so it opens and closes without state, closes on Escape
 * for free, and its items are links to places that navigate anyway.
 *
 * The reader is a `<Link>`: `/reader/:id` is a React route now (the Python
 * handover is closed), so client-side navigation keeps the reading settings
 * query warm instead of reloading the app. The download stays a plain
 * anchor — it is a backend file path, and the router would swallow it and
 * land the reader on a placeholder. The monitor is a React route too, so it
 * is a `<Link>` as well.
 */
function BookMenu({ book }: { book: LibraryBook }) {
  const client = useQueryClient()
  const { t } = useLanguage()
  const active = activeVariant(book)
  const readable = readableVariant(book)

  const remove = useMutation({
    mutationFn: () => api.archiveBook(book.id),
    onSuccess: () => {
      // A deletion moves the book out of every bucket, so the counts, the
      // spotlights and the list all change. Invalidation is by prefix on
      // purpose: a per-query key would leave a figure that no longer adds up.
      void client.invalidateQueries({ queryKey: ['library'] })
    },
  })

  // Shelving is reading state, not translation state: moving a book to
  // "finished" never touches its translation status, and the badge for it
  // renders beside — never instead of — the translation badge in the row.
  const shelf = bookShelf(book)
  const moveShelf = useMutation({
    mutationFn: (next: LibraryShelf | null) => api.setShelf(book.id, next),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['library'] })
    },
  })

  const canDelete = active?.status !== 'running' && active?.status !== 'queued'

  const runDelete = () => {
    if (
      !window.confirm(
        t('library.deleteConfirm', { title: book.title }),
      )
    ) {
      return
    }
    remove.mutate()
  }

  return (
    <details className="lib-menu">
      <summary aria-label={t('library.optionsFor', { title: book.title })} title={t('library.options')}>
        …
      </summary>
      <div className="lib-menu-list">
        {readable ? (
          <Link to={readable.reader}>
            <NavIcon name="reader" size={16} />
            {t('dashboard.read')}
          </Link>
        ) : null}
        {active?.job_id ? (
          <Link to={`/jobs/${active.job_id}`}>
            <NavIcon name="monitor" size={16} />
            {t('nav.jobs')}
          </Link>
        ) : null}
        {active?.download ? (
          <a href={active.download}>
            <NavIcon name="convert" size={16} />
            {t('library.download')}
          </a>
        ) : null}
        {canDelete ? (
          <>
            <span className="lib-menu-sep" aria-hidden="true" />
            <label className="lib-menu-shelf">
              <span>{t('library.shelf.set')}</span>
              <select
                value={shelf ?? ''}
                disabled={moveShelf.isPending}
                onChange={(event) => {
                  const value = event.target.value
                  moveShelf.mutate(value === '' ? null : (value as LibraryShelf))
                }}
              >
                <option value="">{t('library.shelf.none')}</option>
                <option value="want">{t('library.shelf.want')}</option>
                <option value="reading">{t('library.shelf.reading')}</option>
                <option value="finished">{t('library.shelf.finished')}</option>
              </select>
            </label>
            <button
              type="button"
              className="lib-menu-danger"
              onClick={runDelete}
              disabled={remove.isPending}
            >
              {t('library.deleteBook')}
            </button>
          </>
        ) : null}
      </div>
    </details>
  )
}

/** One book in the list. */
function BookRow({ book }: { book: LibraryBook }) {
  const { t } = useLanguage()
  const active = activeVariant(book)
  const chunks = chunkProgress(active)
  const percent = percentOf(active)
  const status = active?.status ?? book.status
  const shelf = bookShelf(book)
  const tags = bookTags(book)

  return (
    <li className="surface-card p-4">
      {/* Three columns on a wide screen -- the book's own block, its progress,
          and the menu -- collapsing to one below `lg`.

          A grid and not a wrapping flex row: as a flex row the title took the
          full width and the badges dropped underneath at the far edge, so a book
          with four badges had a line of title, a line of badges, and a gap
          between them the width of the screen. A grid gives the title and its
          badges one cell, so they cannot come apart.

          The cover is inside the first cell rather than beside it, because a
          third column for a 48px tile would take its width from the title on
          every screen down to the narrowest one. */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-start lg:gap-4">
        <div className="flex min-w-0 gap-[var(--spacing-3)]">
          <BookCover book={book} />
          <div className="min-w-0">
            <strong className="lib-title">{book.title}</strong>
            <span className="lib-meta">
              {extensionOf(book)} · {faBytes(book.size_bytes)}
              {book.author ? ` · ${book.author}` : ''} · {faAgo(book.updated_at)}
            </span>
            <span className="lib-badges">
              {book.translated ? <span className="badge badge-success">{t('library.translatedBadge')}</span> : null}
              {book.readable ? <span className="badge badge-info">{t('library.readableBadge')}</span> : null}
              <span className={badgeClass(status)}>{bookStatusLabel(t, status)}</span>
              {shelf ? (
                <span className={shelf === 'finished' ? 'badge badge-success' : 'badge badge-info'}>
                  {shelfLabel(t, shelf)}
                </span>
              ) : null}
              {tags.map((tag) => (
                <span key={tag} className="badge">
                  #{tag}
                </span>
              ))}
              {(book.variants ?? []).map((variant) => (
                <span key={variant.id} className="badge">
                  {kindLabel(t, variant.kind)}
                </span>
              ))}
            </span>
          </div>
        </div>

        <div className="min-w-0 lg:w-64">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${percent ?? 0}%` }} />
          </div>
          <span className="lib-progress-line">
            <span className="lib-progress-figure">
              {chunks ? t('library.chunksOf', { done: fa(chunks.completed), total: fa(chunks.total) }) : t('library.noChunkCount')}
            </span>
            <span className="lib-progress-figure">
              {percent === null ? '—' : t('library.percent', { percent: fa(percent) })}
            </span>
          </span>
        </div>

        <BookMenu book={book} />
      </div>
    </li>
  )
}

/** The two cards between the figures and the list. */
function Spotlight({
  books,
  total,
}: {
  books: LibraryBook[]
  total: number
}) {
  const { t } = useLanguage()
  const ladder = progressLadder(books, 5)
  const last = lastReadable(books)
  const furthest = furthestProgress(books)

  return (
    <section aria-label={t('library.spotlight')} className="lib-spot mb-[var(--spacing-6)]">
      {/* Which half-done book is closest to being worth finishing. The bars are
          the same percent, in the same order, as the leader -- so the tallest
          bar is always the book named below it. */}
      <div className="lib-spot-card">
        <div className="lib-spot-head">
          <h2 className="lib-spot-title">{t('library.mostProgress')}</h2>
          <span className="lib-spot-note">
            {ladder.length > 0 ? t('library.unfinishedBooks', { count: fa(ladder.length) }) : t('library.noUnfinished')}
          </span>
        </div>
        {furthest ? (
          <>
            <div className="lib-bars" aria-hidden="true">
              {ladder.map((row) => (
                <span
                  key={row.book.id}
                  className="lib-bar"
                  style={{ ['--bar-height' as string]: `${Math.max(4, row.percent)}%` }}
                />
              ))}
            </div>
            <strong className="lib-title mt-[var(--spacing-3)]">{furthest.book.title}</strong>
            <span className="lib-meta">
              {t('library.percentTranslated', { percent: fa(furthest.percent) })} · {t('monitor.chunks.count', { n: fa(furthest.variant.progress.total) })}
            </span>
          </>
        ) : (
          <p className="lib-spot-note mt-[var(--spacing-3)]">
            {t('library.allDoneSpot', { total: fa(total) })}
          </p>
        )}
      </div>

      {/* What was last read, and the one action that continues it. */}
      <div className="lib-spot-card">
        <div className="lib-spot-head">
          <h2 className="lib-spot-title">{t('library.continueLast')}</h2>
          <span className="lib-spot-note">
            {last ? faAgo(last.book.updated_at) : t('library.neverRead')}
          </span>
        </div>
        {last ? (
          <>
            <strong className="lib-title mt-[var(--spacing-3)]">{last.book.title}</strong>
            <span className="lib-meta">
              {t('library.percent', { percent: fa(last.percent) })} · {extensionOf(last.book)} · {faBytes(last.book.size_bytes)}
            </span>
            <div className="mt-[var(--spacing-3)] progress-track">
              <div className="progress-fill" style={{ width: `${last.percent}%` }} />
            </div>
            {/* A `Link`: `/reader/:id` is a React route now, so this stays
                in the app instead of reloading it through the backend. */}
            <Link className="btn btn-secondary mt-[var(--spacing-4)]" to={last.variant.reader}>
              {t('library.readBilingual')}
            </Link>
          </>
        ) : (
          <p className="lib-spot-note mt-[var(--spacing-3)]">
            {t('library.noReadable')}
          </p>
        )}
      </div>
    </section>
  )
}

export function LibraryPage() {
  const { t, dir } = useLanguage()
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<LibraryStatusFilter | ''>('')
  const [rawQuery, setRawQuery] = useState('')
  const [query, setQuery] = useState('')
  // Reading shelf and tag ride the same server-side filtering as `status`:
  // the endpoint understands `shelf` and `tag`, so these are values the list
  // asks for rather than a client-side guess over one page.
  const [shelfFilter, setShelfFilter] = useState<LibraryShelf | ''>('')
  const [rawTag, setRawTag] = useState('')
  const [tag, setTag] = useState('')

  // Debounce: 300ms is short enough to feel live and long enough that a fast
  // typist does not produce eight requests.
  const onQuery = (value: string) => {
    setRawQuery(value)
    window.clearTimeout(onQuery.timer)
    onQuery.timer = window.setTimeout(() => {
      setQuery(value)
      setPage(1)
    }, 300)
  }
  onQuery.timer = 0

  const onTag = (value: string) => {
    setRawTag(value)
    window.clearTimeout(onTag.timer)
    onTag.timer = window.setTimeout(() => {
      setTag(value)
      setPage(1)
    }, 300)
  }
  onTag.timer = 0

  const counts = useQuery({
    queryKey: ['library', 'counts'],
    queryFn: () => api.library(1, 1),
    staleTime: 30_000,
  })
  const running = useQuery({
    queryKey: ['library', 'counts', 'running'],
    queryFn: () => api.library(1, 1, '', 'running'),
    staleTime: 30_000,
  })
  const completed = useQuery({
    queryKey: ['library', 'counts', 'completed'],
    queryFn: () => api.library(1, 1, '', 'completed'),
    staleTime: 30_000,
  })
  // The `failed` bucket gets its own request rather than being derived, because
  // the tab above it is server-filtered: a derived number would say "15 ناتمام"
  // over a list the endpoint then fills with 11. Both numbers have to come from
  // the same filter to agree on screen.
  const failed = useQuery({
    queryKey: ['library', 'counts', 'failed'],
    queryFn: () => api.library(1, 1, '', 'failed'),
    staleTime: 30_000,
  })
  // The wide page, for the two cards only. See `SPOTLIGHT_LIMIT`.
  const spotlight = useQuery({
    queryKey: ['library', 'spotlight'],
    queryFn: () => api.library(1, SPOTLIGHT_LIMIT),
    staleTime: 30_000,
  })
  const books = useQuery({
    queryKey: ['library', 'list', page, query, filter, shelfFilter, tag],
    queryFn: () => api.library(page, PAGE_SIZE, query, filter, shelfFilter, tag),
    placeholderData: (previous) => previous,
  })
  // Pages per day and the reading streak. Polled on a slower cadence than the
  // list: it moves when the reader reports progress, not when they type.
  const reading = useQuery({
    queryKey: ['library', 'reading-stats'],
    queryFn: () => api.readingStats(30),
    staleTime: 60_000,
  })

  const stats = libraryStats({
    total: counts.data?.total ?? 0,
    running: running.data?.total ?? 0,
    completed: completed.data?.total ?? 0,
    failed: failed.data?.total ?? 0,
  })

  const items = books.data?.items ?? []
  const total = books.data?.total ?? 0
  const pages = pageCount(total, books.data?.limit ?? PAGE_SIZE)
  const range = pageRange(page, books.data?.limit ?? PAGE_SIZE, total)
  const activity = recentActivity(spotlight.data?.items ?? [])

  const chooseFilter = (key: LibraryStatusFilter | '') => {
    setFilter(key)
    setPage(1)
  }

  const chooseShelf = (key: LibraryShelf | '') => {
    setShelfFilter(key)
    setPage(1)
  }

  const isEmptyLibrary = !counts.isPending && stats.total === 0

  return (
    <main className="page" dir={dir}>
      {/* 0. The heading, on a band of its own. */}
      <header className="library-hero mb-[var(--spacing-6)]">
        <p className="library-hero-eyebrow">{t('library.eyebrow')}</p>
        <h1 className="library-hero-title">{t('library.title')}</h1>
        <p className="library-hero-sub">
          {t('library.subtitle')}
        </p>
        <div className="mt-[var(--spacing-5)] flex flex-wrap gap-[var(--spacing-2)]">
          <Link to="/workspace" className="btn btn-secondary">
            {t('dashboard.addBook')}
          </Link>
          <Link to="/jobs" className="btn btn-secondary">
            {t('library.jobsLink')}
          </Link>
        </div>
      </header>

      {isEmptyLibrary ? (
        <section className="surface-card p-[var(--spacing-5)]">
          <h2 className="text-[length:var(--text-h3)] font-extrabold">{t('library.emptyTitle')}</h2>
          <p
            className="mt-[var(--spacing-2)] text-[length:var(--text-small)]"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {t('library.emptyBody')}
          </p>
          <Link to="/workspace" className="btn btn-primary mt-[var(--spacing-4)]">
            {t('dashboard.addBook')}
          </Link>
        </section>
      ) : (
        <>
          {/* 1. Four figures. */}
          <section aria-label={t('library.summary')} className="mb-[var(--spacing-6)]">
            <div className="grid grid-cols-2 gap-[var(--spacing-3)] lg:grid-cols-4">
              <Tile
                icon="library"
                label={t('library.inLibrary')}
                value={fa(stats.total)}
                hint={
                  stats.unfinished > 0
                    ? t('library.unfinishedVolumes', { count: fa(stats.unfinished) })
                    : t('library.allDone')
                }
                bar={stats.completedShare}
              />
              <Tile
                icon="monitor"
                label={t('dashboard.running')}
                value={fa(stats.running)}
                hint={stats.running > 0 ? t('dashboard.runningHint') : t('library.noRunning')}
                bar={stats.total > 0 ? Math.round((stats.running / stats.total) * 100) : 0}
              />
              <Tile
                icon="reader"
                label={t('library.fullyTranslated')}
                value={fa(stats.completed)}
                hint={
                  stats.completedShare === null
                    ? '—'
                    : t('library.shareOfLibrary', { share: fa(stats.completedShare) })
                }
                bar={stats.completedShare}
              />
              <Tile
                icon="add"
                label={t('library.unfinished')}
                value={fa(stats.unfinished)}
                hint={
                  stats.unfinished === 0
                    ? t('library.nothingToResume')
                    : t('library.waitingForYou', { count: fa(stats.unfinished) })
                }
                bar={
                  stats.total > 0 ? Math.round((stats.unfinished / stats.total) * 100) : 0
                }
              />
            </div>
          </section>

          {/* 2. Two answers, not two more statistics. */}
          <Spotlight books={spotlight.data?.items ?? []} total={stats.total} />

          {/* 3. The list: filter, search, and the last time anything moved. */}
          <section className="surface-card p-[var(--spacing-4)]" aria-label={t('library.list')}>
            <div className="mb-[var(--spacing-3)] flex flex-wrap items-baseline justify-between gap-[var(--spacing-3)]">
              <h2 className="text-[length:var(--text-h3)] font-extrabold">{t('library.myBooks')}</h2>
              <span
                className="text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {counts.data
                  ? t('library.diskFree', { free: faBytes(counts.data.storage.free) })
                  : t('library.readingDisk')}
              </span>
            </div>

            {/* Two rows rather than one. `control-row` is what lets the field
                take the free width and the row break instead of pushing its
                neighbour off the edge of a 393px screen, and that only works
                while the field is a direct child of it -- so the field gets a
                row to itself and the tabs get the other. */}
            <div className="control-row mb-[var(--spacing-3)]">
              <input
                type="search"
                className="field"
                value={rawQuery}
                onChange={(event) => onQuery(event.target.value)}
                placeholder={t('library.searchPh')}
                aria-label={t('library.searchAria')}
              />
              <select
                className="field"
                value={shelfFilter}
                onChange={(event) => chooseShelf(event.target.value as LibraryShelf | '')}
                aria-label={t('library.shelf.label')}
              >
                <option value="">{t('library.shelf.all')}</option>
                <option value="want">{t('library.shelf.want')}</option>
                <option value="reading">{t('library.shelf.reading')}</option>
                <option value="finished">{t('library.shelf.finished')}</option>
              </select>
              <input
                type="search"
                className="field"
                value={rawTag}
                onChange={(event) => onTag(event.target.value)}
                placeholder={t('library.tagPh')}
                aria-label={t('library.tagAria')}
              />
              <span
                className="text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {activity ? t('library.lastActivity', { date: faDate(activity) }) : t('library.noActivity')}
                {reading.data && reading.data.total_pages > 0
                  ? ` · ${t('library.readingLine', { avg: fa(reading.data.avg_per_day), streak: fa(reading.data.streak_days) })}`
                  : ''}
              </span>
            </div>

            <div className="mb-[var(--spacing-4)]">
              <div className="lib-tabs" role="group" aria-label={t('monitor.chunks.filterAria')}>
                {LIBRARY_TABS.map((tab) => (
                  <button
                    key={tab.key || 'all'}
                    type="button"
                    className="lib-tab"
                    aria-pressed={filter === tab.key}
                    onClick={() => chooseFilter(tab.key)}
                  >
                    {tab.key === '' ? t('library.tab.all') : statusLabel(tab.key)}
                    <span className="lib-tab-count">{fa(stats[tab.count])}</span>
                  </button>
                ))}
              </div>
            </div>

            {books.isError ? (
              <p role="alert" className="alert alert-error">
                {t('library.loadError')}
              </p>
            ) : books.isPending ? (
              <ul className="grid gap-[var(--spacing-2)]">
                {Array.from({ length: 5 }, (_, index) => (
                  <li key={index}>
                    <div className="skeleton" style={{ height: 84 }} />
                  </li>
                ))}
              </ul>
            ) : items.length === 0 ? (
              <p className="empty">
                {query
                  ? t('library.noSearchResult')
                  : t('library.noBooksInRange')}
              </p>
            ) : (
              <ul className="grid gap-[var(--spacing-2)]" style={{ opacity: books.isFetching ? 0.6 : 1 }}>
                {items.map((book) => (
                  <BookRow key={book.id} book={book} />
                ))}
              </ul>
            )}

            <div className="lib-foot mt-[var(--spacing-4)]">
              <span>
                {t('library.showing', { from: fa(range.from), to: fa(range.to), total: fa(total) })}
              </span>
              {pages > 1 ? (
                <span className="flex items-center gap-[var(--spacing-2)]">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={page <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    {t('library.prev')}
                  </button>
                  <span className="tabular-nums">
                    {t('library.pageOf', { page: fa(page), pages: fa(pages) })}
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={page >= pages}
                    onClick={() => setPage((value) => Math.min(pages, value + 1))}
                  >
                    {t('library.next')}
                  </button>
                </span>
              ) : null}
            </div>
          </section>
        </>
      )}
    </main>
  )
}