import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChunkRow } from '@/lib/chunks'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { FALLBACK_VIEWPORT, ROW_H, computeWindow } from '@/lib/virtual'
import { CHUNK_COLUMNS } from '@/lib/chunks-columns'

/**
 * Windowed chunk table.
 *
 * A 400-chunk book renders ~400 rows of bilingual text, which is enough DOM to
 * make scrolling stutter. The Python page solves this with a fixed row height
 * and two spacer rows; the same arithmetic is reproduced here so the two UIs
 * scroll identically.
 *
 *   ROW_H   fixed height, so the visible range is pure arithmetic
 *   OVERSCAN extra rows either side, so a fast scroll never shows blank
 *
 * The row height is fixed rather than measured because the CSS pins it with a
 * fixed `height` plus `overflow: hidden`. If the text is allowed to wrap freely
 * the arithmetic breaks and rows overlap, so the height is set on the element
 * and not left to the content.
 *
 * The arithmetic itself lives in `@/lib/virtual` so it can be tested without a
 * DOM. An off-by-one there does not throw, it renders blank space.
 */

export interface VirtualChunkTableProps {
  rows: ChunkRow[]
  /** Shown instead of the table when there are no rows at all. */
  emptyAll: string
  /** Shown when rows exist but the filters exclude them all. */
  emptyFiltered: string
  /**
   * Change this to scroll back to the top.
   *
   * The scroll container lives inside this component, so the parent cannot
   * reach it with a ref without threading one through. Incrementing a token is
   * simpler and cannot desynchronise from the filter state.
   */
  resetToken?: number
}

function Row({ row }: { row: ChunkRow }) {
  const { t } = useLanguage()
  const translated = row.target !== ''
  return (
    <tr style={{ height: ROW_H }} data-flagged={row.flagged}>
      <td data-label={CHUNK_COLUMNS.id.label} style={{ width: CHUNK_COLUMNS.id.width }}>
        <span className="chunk-id">{row.id}</span>
        {row.chapter ? <div className="chunk-id" style={{ marginTop: 4 }}>{row.chapter}</div> : null}
      </td>
      <td data-label={CHUNK_COLUMNS.source.label} style={{ width: CHUNK_COLUMNS.source.width }}>
        <div className="chunk-text" dir="ltr">
          {row.source}
        </div>
      </td>
      <td data-label={CHUNK_COLUMNS.target.label} style={{ width: CHUNK_COLUMNS.target.width }}>
        {translated ? (
          <div className="chunk-text" dir="rtl">
            {row.target}
          </div>
        ) : (
          <span style={{ color: 'var(--color-text-muted)' }}>—</span>
        )}
      </td>
      <td data-label={CHUNK_COLUMNS.status.label} style={{ width: CHUNK_COLUMNS.status.width }}>
        {row.flagged ? (
          <span className="flag-pill">{t('monitor.table.flagged')}</span>
        ) : translated ? (
          <span className="badge badge-completed">{t('monitor.table.done')}</span>
        ) : (
          <span className="badge badge-queued">{t('monitor.table.pending')}</span>
        )}
        {row.notes.length > 0 ? (
          <div style={{ marginTop: 6 }}>
            {row.notes.map((note) => (
              <span key={note} className="flag-pill">
                {note}
              </span>
            ))}
          </div>
        ) : null}
      </td>
    </tr>
  )
}

export function VirtualChunkTable({
  rows,
  emptyAll,
  emptyFiltered,
  resetToken = 0,
}: VirtualChunkTableProps) {
  const scroller = useRef<HTMLDivElement | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [viewport, setViewport] = useState(FALLBACK_VIEWPORT)

  // The visible range depends on the container height, which is not known on
  // first paint. A ResizeObserver tracks it so a window resize or a tab change
  // recomputes instead of leaving a half-empty window.
  useEffect(() => {
    const element = scroller.current
    if (!element) return
    const measure = () => setViewport(element.clientHeight || FALLBACK_VIEWPORT)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // A filter change can shrink the list under the viewport. Staying where the
  // user was leaves them past the end, so the top is restored.
  //
  // Only the DOM is touched here. Assigning scrollTop fires a scroll event,
  // which calls onScroll and updates the state, so calling setScrollTop
  // directly would be a second render for no reason -- and the React Compiler
  // linter is right that state updates belong in the event, not an effect.
  useEffect(() => {
    const element = scroller.current
    if (element && element.scrollTop !== 0) element.scrollTop = 0
  }, [resetToken])

  // `passive` because scrolling must never be blocked by a listener that only
  // sets state.
  const onScroll = useCallback(() => {
    const element = scroller.current
    if (element) setScrollTop(element.scrollTop)
  }, [])

  const visible = computeWindow(rows, scrollTop, viewport)
  const { padTop, padBottom } = visible

  if (rows.length === 0) {
    return (
      <div ref={scroller} className="empty" style={{ padding: 32 }}>
        {emptyAll}
      </div>
    )
  }

  return (
    <div
      ref={scroller}
      onScroll={onScroll}
      className="vtable-wrap"
      // Only the windowed rows are in the accessibility tree, and the real
      // total is announced instead of the handful that happen to be painted.
      aria-rowcount={rows.length + 1}
    >
      <table className="vtable">
        <thead>
          <tr>
            <th scope="col">{CHUNK_COLUMNS.id.label}</th>
            <th scope="col">{CHUNK_COLUMNS.source.label}</th>
            <th scope="col">{CHUNK_COLUMNS.target.label}</th>
            <th scope="col">{CHUNK_COLUMNS.status.label}</th>
          </tr>
        </thead>
        <tbody>
          {padTop > 0 ? (
            <tr style={{ height: padTop }} aria-hidden="true">
              <td colSpan={4} />
            </tr>
          ) : null}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={4}>
                <div className="empty">{emptyFiltered}</div>
              </td>
            </tr>
          ) : (
            visible.rows.map((row) => <Row key={row.id} row={row} />)
          )}
          {padBottom > 0 ? (
            <tr style={{ height: padBottom }} aria-hidden="true">
              <td colSpan={4} />
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  )
}

/** Exposed so the count readout and the table cannot drift apart. */

/** A short summary for the QA tab, matching the Python `flagged.slice(0, 50)`. */
export function FlaggedList({ rows }: { rows: ChunkRow[] }) {
  const { t } = useLanguage()
  const flagged = rows.filter((row) => row.flagged)
  if (flagged.length === 0) return null
  return (
    <div style={{ marginTop: 16 }}>
      <ul className="flagged-list">
        {flagged.slice(0, 50).map((row) => (
          <li key={row.id} className="flagged-item">
            <div className="chunk-id" style={{ marginBottom: 6 }}>
              {row.id}
              {row.chapter ? ` · ${row.chapter}` : ''}
            </div>
            {row.notes.map((note) => (
              <span key={note} className="flag-pill">
                {note}
              </span>
            ))}
            <div className="chunk-text" dir="rtl" style={{ marginTop: 8 }}>
              {row.target || row.source}
            </div>
          </li>
        ))}
      </ul>
      {flagged.length > 50 ? (
        <p className="text-[length:var(--text-label)]" style={{ marginTop: 10, color: 'var(--color-text-muted)' }}>
          {t('monitor.table.more', { n: fa(flagged.length - 50) })}
        </p>
      ) : null}
    </div>
  )
}
