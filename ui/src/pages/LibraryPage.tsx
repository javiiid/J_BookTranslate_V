import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { LibraryBook } from '@/lib/api'
import { fa, faBytes, faDate } from '@/lib/format'

/**
 * The library.
 *
 * Ported from `app/library/view.py`. The list is paged server-side because a
 * long-running install accumulates hundreds of books; the search box is
 * debounced into the query key rather than fired per keystroke, so typing does
 * not spam the API.
 *
 * `job_id` on a variant is the link to the monitor, which is the fastest path
 * from "a book exists" to "what is happening to it".
 */

const STATUS_FA: Record<string, string> = {
  queued: 'در صف',
  running: 'در حال ترجمه',
  paused: 'متوقف‌شده',
  stopped: 'متوقف‌شده',
  completed: 'تکمیل‌شده',
  failed: 'خطادار',
  cancelled: 'لغوشده',
}

const STATUS_TONE: Record<string, string> = {
  queued: 'badge',
  running: 'badge badge-accent',
  paused: 'badge badge-warning',
  stopped: 'badge badge-warning',
  completed: 'badge badge-success',
  failed: 'badge badge-error',
  cancelled: 'badge',
}

const KIND_FA: Record<string, string> = {
  original: 'اصلی',
  translated: 'ترجمه‌شده',
  main: 'اصلی',
}

function BookRow({ book }: { book: LibraryBook }) {
  const variants = book.variants ?? []
  const active = variants.find((variant) => variant.status === 'running')
    ?? variants[0]
  /* Where "read it" goes. The translated copy is the one a reader of this
     tool wants, so it wins; an untranslated book still opens in its original
     language rather than offering nothing. */
  const readable =
    variants.find((variant) => variant.kind === 'translated' && variant.is_readable && variant.reader)
    ?? variants.find((variant) => variant.is_readable && variant.reader)

  return (
    <li className="surface-card p-4">
      {/* Stacked, not side by side, below `lg`.

          As a `flex-wrap` row the title took the full width and the badges
          dropped underneath at the far edge, so a book with three badges had a
          line of title, a line of badges, and a gap between them the width of
          the screen. A grid gives the title its own row and the badges their
          own, and above `lg` they sit on one line again with the badges pushed
          to the end. */}
      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start lg:gap-3">
        <div className="min-w-0">
          <strong className="block truncate text-[length:var(--text-body)]">{book.title}</strong>
          <span
            className="block text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {book.author || 'نویسنده نامشخص'} · {faBytes(book.size_bytes)} ·{' '}
            {faDate(book.updated_at)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {book.translated ? <span className="badge badge-success">ترجمه‌شده</span> : null}
          {/* A plain `<a>`, never `<Link>`: `reader` is a backend path and the
              router would swallow it. Before, "readable" was a badge -- a
              statement about the book with nothing to press -- while the
              landing page promises reading "from the library". */}
          {readable ? (
            <a href={readable.reader} className="btn btn-secondary">
              مطالعه
            </a>
          ) : book.readable ? (
            <span className="badge badge-info">قابل مطالعه</span>
          ) : null}
          {active ? (
            <span className={STATUS_TONE[active.status] ?? 'badge'}>
              {STATUS_FA[active.status] ?? active.status}
            </span>
          ) : null}
        </div>
      </div>

      {variants.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {variants.map((variant) => (
            <li key={variant.id}>
              {variant.job_id ? (
                <Link
                  to={`/jobs/${variant.job_id}`}
                  className="badge"
                  style={{ textDecoration: 'none' }}
                >
                  {KIND_FA[variant.kind] ?? variant.kind} · {faBytes(variant.size_bytes)}
                </Link>
              ) : (
                <span className="badge">
                  {KIND_FA[variant.kind] ?? variant.kind} · {faBytes(variant.size_bytes)}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p
          className="mt-3 text-[length:var(--text-caption)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          هنوز نسخه‌ای برای این کتاب ساخته نشده است.
        </p>
      )}

      {active?.progress && active.progress.total > 0 ? (
        <div className="mt-3">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${Math.round((active.progress.completed / active.progress.total) * 100)}%`,
              }}
            />
          </div>
          <span
            className="mt-1 block text-[length:var(--text-caption)] tabular-nums"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {fa(active.progress.completed)} از {fa(active.progress.total)} بخش
          </span>
        </div>
      ) : null}
    </li>
  )
}

export function LibraryPage() {
  const [page, setPage] = useState(1)
  const [rawQuery, setRawQuery] = useState('')
  const [query, setQuery] = useState('')

  // Debounce: 300ms is short enough to feel live and long enough that a fast
  // typist does not produce eight requests. The timer lives in a ref, not on
  // the callback: re-creating the callback every render used to reset the id
  // to 0, so `clearTimeout` never cleared and keystrokes fired overlapping
  // timers.
  const timer = useRef(0)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const onQuery = (value: string) => {
    setRawQuery(value)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      setQuery(value)
      setPage(1)
    }, 300)
  }

  const books = useQuery({
    queryKey: ['library', page, query],
    queryFn: () => api.library(page, 12, query),
    placeholderData: (previous) => previous,
  })

  const total = books.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / (books.data?.limit ?? 12)))

  return (
    <main className="page" dir="rtl">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">کتابخانه</h1>
          <p
            className="mt-1 text-[length:var(--text-small)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {books.isPending ? 'در حال بارگذاری…' : `${fa(total)} کتاب`}
            {books.data ? ` · ${faBytes(books.data.storage.free)} فضای آزاد` : ''}
          </p>
        </div>
        {/* `control-row` rather than a plain flex row: this carried a `w-64`
            field, which is 16rem of input plus a button inside a row that could
            not wrap -- wider than a 393px viewport, so the button ran off the
            edge. The field now takes the free width and the row breaks instead. */}
        <div className="control-row">
          <input
            type="search"
            className="field"
            value={rawQuery}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="جست‌وجوی کتاب…"
            aria-label="جست‌وجوی کتاب"
          />
          <Link to="/workspace" className="btn btn-primary">
            افزودن کتاب
          </Link>
        </div>
      </header>

      {books.isError ? (
        <p role="alert" className="alert alert-error">
          دریافت کتابخانه ممکن نشد. مطمئن شوید سرور پایتون روی ۸۷۶۵ اجرا است.
        </p>
      ) : books.isPending ? (
        <ul className="grid gap-3">
          {Array.from({ length: 4 }, (_, index) => (
            <li key={index}>
              <div className="skeleton" style={{ height: 96 }} />
            </li>
          ))}
        </ul>
      ) : (books.data?.items.length ?? 0) === 0 ? (
        <p className="empty">
          {query ? 'کتابی با این جست‌وجو پیدا نشد.' : 'کتابخانه خالی است. یک کتاب اضافه کنید.'}
        </p>
      ) : (
        <ul className="grid gap-3" style={{ opacity: books.isFetching ? 0.6 : 1 }}>
          {(books.data?.items ?? []).map((book) => (
            <BookRow key={book.id} book={book} />
          ))}
        </ul>
      )}

      {pages > 1 ? (
        <nav className="mt-6 flex items-center justify-center gap-3" aria-label="صفحه‌بندی">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            قبلی
          </button>
          <span
            className="text-[length:var(--text-label)] tabular-nums"
            style={{ color: 'var(--color-text-muted)' }}
          >
            صفحهٔ {fa(page)} از {fa(pages)}
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={page >= pages}
            onClick={() => setPage((value) => Math.min(pages, value + 1))}
          >
            بعدی
          </button>
        </nav>
      ) : null}
    </main>
  )
}
