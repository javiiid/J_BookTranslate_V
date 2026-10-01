/**
 * The chunk table's columns, and the row height it is measured against.
 *
 * ## Why this is a `.ts` and not a `.tsx`
 *
 * It holds no JSX. It is imported by `VirtualChunkTable.tsx` for the widths and
 * the labels, and by `tests/monitor.test.ts` for the arithmetic -- and
 * `node --test` cannot load a `.tsx` at all, so a declaration that lives in the
 * component cannot be asserted on. The test needs the real numbers, not a copy
 * of them, or it is checking its own transcription.
 *
 * ## Why the widths and the labels are one declaration
 *
 * They used to be two, and in two places: inline `style` on every `td`, and a
 * second set in `tokens.css`. An inline style beats a class at any specificity,
 * so the mobile rules could never apply -- the table was authored to be exactly
 * as hard to override as it needed to be overridden.
 *
 * Keeping them together also means a header cell and its stacked counterpart
 * cannot disagree. Below `sm` the table reflows into labelled blocks, and a
 * label that lives only in a `th` disappears the moment the `th` is visually
 * hidden.
 *
 * ## The numbers, measured at 393px
 *
 * The `.page` gutter is 16px a side, so 361px is available. Four columns with no
 * widths divide that evenly: **90px each**. A Persian word at 14px is about 10
 * characters in 90px, and the widest label here is 14 characters. That is the
 * reported problem, and it is why the fix is a reflow below 640px rather than a
 * different set of percentages: no split of 361px makes four columns readable.
 */

/** A column of the chunk table. */
export interface ChunkColumn {
  /** Stable identity, for a key. */
  key: 'id' | 'source' | 'target' | 'status'
  /** The header text, and the label a reflowed cell prints for itself. */
  label: string
  /** Percentage of the table's width. The four must total 100. */
  width: string
}

/**
 * The columns, in render order.
 *
 * The two text columns take the space the two short ones do not need: a chunk id
 * and a status badge are both short, and the text is the point of the table.
 */
export const CHUNK_COLUMNS = {
  id: { key: 'id', label: 'بخش', width: '16%' },
  source: { key: 'source', label: 'متن اصلی', width: '35%' },
  target: { key: 'target', label: 'ترجمهٔ نهایی', width: '35%' },
  status: { key: 'status', label: 'وضعیت', width: '14%' },
} as const satisfies Record<string, ChunkColumn>

/** The columns in render order, for iteration. */
export const CHUNK_COLUMN_LIST: readonly ChunkColumn[] = [
  CHUNK_COLUMNS.id,
  CHUNK_COLUMNS.source,
  CHUNK_COLUMNS.target,
  CHUNK_COLUMNS.status,
]

/** The narrowest phone the layout is held to. */
export const NARROWEST_VIEWPORT = 393
/** Tailwind's `sm`, below which the table reflows. */
export const REFLOW_BELOW = 640
/** The `.page` inline gutter at the narrow width, a side. */
export const NARROW_GUTTER = 16

/**
 * The width each column gets under an even split, which is what the browser did
 * before the columns were declared. Kept because it is the number the fix is
 * measured against, and a test that stops describing the problem should fail.
 */
export function evenSplit(
  viewport: number = NARROWEST_VIEWPORT,
  columns: number = CHUNK_COLUMN_LIST.length,
): number {
  return Math.floor((viewport - NARROW_GUTTER * 2) / columns)
}

/**
 * Vazirmatn at 12px averages about 6.2px per Persian character.
 *
 * An estimate, and labelled as one: it is used to check that a column is
 * obviously too narrow for its label, not to lay anything out. A character
 * count would be a worse proxy, because Persian letters join and the joined
 * forms are not the sum of the isolated ones.
 */
export const PX_PER_CHARACTER_AT_12PX = 6.2
