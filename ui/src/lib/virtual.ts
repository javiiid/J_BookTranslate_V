/**
 * Window arithmetic for the virtualised chunk table.
 *
 * Kept pure and separate from the component so it can be tested without a
 * DOM. This is the part most likely to be subtly wrong: an off-by-one here does
 * not throw, it renders blank space at the end of a long book, which is easy
 * to miss and annoying to diagnose.
 *
 * The constants mirror `app/jobs/detail_page.py` (`ROW_H = 96, OVERSCAN = 6`)
 * and the `height: 96px` in `tokens.css`. All three must agree; the test below
 * checks the arithmetic, the comment on `.vtable td` checks the CSS.
 */
export const ROW_H = 96
export const OVERSCAN = 6

/** Fallback viewport height before the container has been measured. */
export const FALLBACK_VIEWPORT = 520

export interface Window<T> {
  /** Index of the first rendered row, into the filtered list. */
  start: number
  /** Index after the last rendered row. */
  end: number
  /** Spacer height above the rows, in pixels. */
  padTop: number
  /** Spacer height below the rows, in pixels. */
  padBottom: number
  /** The rows to actually render. */
  rows: readonly T[]
  /** Rows deliberately not rendered, for the accessibility summary. */
  hidden: number
}

export function computeWindow<T>(
  rows: readonly T[],
  scrollTop: number,
  viewport: number,
  rowHeight = ROW_H,
  overscan = OVERSCAN,
): Window<T> {
  // A negative scrollTop is impossible in the DOM but easy to produce in a
  // test, and it must not produce a negative index.
  const height = Math.max(rowHeight, viewport)
  const visible = Math.ceil(height / rowHeight)

  // Clamp the scroll position to the range the list can actually be scrolled
  // to, the way a browser does. Without this, filtering a long list down to a
  // few rows leaves scrollTop pointing far past the new end and every visible
  // row disappears.
  const maxScroll = Math.max(0, rows.length * rowHeight - height)
  const top = Math.min(Math.max(0, scrollTop), maxScroll)

  // Clamp the start index too, so an out-of-range scrollTop can never produce
  // `slice(98, 50)` and an empty render. This is the case that showed up as
  // "the table is blank at the end of the book".
  const maxStart = Math.max(0, rows.length - 1)
  const start = Math.min(Math.max(0, Math.floor(top / rowHeight) - overscan), maxStart)
  const end = Math.min(rows.length, start + visible + overscan * 2)

  return {
    start,
    end,
    padTop: start * rowHeight,
    // Without Math.max a shorter list would give a negative bottom spacer,
    // which browsers treat as 0 but which makes the scroll height wrong.
    padBottom: Math.max(0, (rows.length - end) * rowHeight),
    rows: rows.slice(start, end),
    hidden: rows.length - (end - start),
  }
}

/**
 * The scroll offset that brings a row index into view, used when a filter
 * changes. Returns 0 when the row is already visible so the caller can skip the
 * assignment entirely.
 */
export function scrollToReveal(
  index: number,
  viewport: number,
  currentTop: number,
  rowHeight = ROW_H,
): number {
  const rowTop = index * rowHeight
  if (rowTop < currentTop) return rowTop
  if (rowTop + rowHeight > currentTop + viewport) {
    return Math.max(0, rowTop - viewport + rowHeight)
  }
  return currentTop
}
