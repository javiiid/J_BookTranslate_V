import { useMemo, useState } from 'react'
import type { JobChunk } from '@/lib/api'
import { type ChunkStateFilter, type ChunkRow, filterChunks, toRow } from '@/lib/chunks'
import { fa } from '@/lib/format'
import { VirtualChunkTable } from './VirtualChunkTable'

const STATES: { value: ChunkStateFilter; label: string }[] = [
  { value: 'all', label: 'همه' },
  { value: 'done', label: 'انجام‌شده' },
  { value: 'pending', label: 'در انتظار' },
  { value: 'flagged', label: 'پرچم‌دار' },
]

export interface ChunksTabProps {
  items: JobChunk[] | undefined
  available: boolean
  isPending: boolean
  isError: boolean
  onRetry: () => void
}

export function ChunksTab({ items, available, isPending, isError, onRetry }: ChunksTabProps) {
  const [query, setQuery] = useState('')
  const [state, setState] = useState<ChunkStateFilter>('all')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  // Bumped on every filter change; the table owns its scroll container and
  // watches this to jump back to the top.
  const [resetToken, setResetToken] = useState(0)
  const touch = () => setResetToken((value) => value + 1)

  // Derived once per response rather than per render: the note extraction is a
  // regex pass over every chunk of the book.
  const rows = useMemo<ChunkRow[]>(() => (items ?? []).map(toRow), [items])

  const filtered = useMemo(
    () => filterChunks(rows, { query, state, flaggedOnly }),
    [rows, query, state, flaggedOnly],
  )

  if (isError) {
    return (
      <div className="surface-card p-[var(--spacing-5)]">
        <p role="alert" className="alert alert-error">
          دریافت بخش‌ها ممکن نشد.
        </p>
        <button type="button" className="btn btn-secondary" onClick={onRetry} style={{ marginTop: 12 }}>
          تلاش دوباره
        </button>
      </div>
    )
  }

  if (isPending) {
    return (
      <div className="surface-card p-[var(--spacing-5)]">
        <ul className="grid gap-[var(--spacing-3)]">
          {Array.from({ length: 6 }, (_, index) => (
            <li key={index}>
              <div className="skeleton" style={{ height: 14 }} />
            </li>
          ))}
        </ul>
      </div>
    )
  }

  // `available` is false when the job has no pipeline state yet, which is a
  // different situation from "has chunks but the filter hid them".
  const emptyAll = available
    ? 'هنوز بخشی برای این کار ساخته نشده است.'
    : 'اطلاعات بخش‌ها در دسترس نیست.'

  return (
    <div className="grid gap-[var(--spacing-3)]">
      <div className="surface-card flex flex-wrap items-center gap-[var(--spacing-3)] p-[var(--spacing-3)]">
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            touch()
          }}
          placeholder="جست‌وجو در مبدأ و ترجمه…"
          aria-label="جست‌وجو در بخش‌ها"
          className="field min-w-0 flex-1 basis-[14rem]"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
        />
        <label className="flex items-center gap-2 text-[length:var(--text-label)]">
          <span style={{ color: 'var(--color-text-muted)' }}>وضعیت</span>
          <select
            value={state}
            onChange={(event) => {
              setState(event.target.value as ChunkStateFilter)
              touch()
            }}
            aria-label="فیلتر وضعیت"
            className="field"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
          >
            {STATES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-[length:var(--text-label)]">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(event) => {
              setFlaggedOnly(event.target.checked)
              touch()
            }}
          />
          فقط پرچم‌دار
        </label>
        <span className="ms-auto text-[length:var(--text-label)] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
          {fa(filtered.length)} بخش
        </span>
      </div>

      {rows.length === 0 ? (
        <div className="surface-card empty">{emptyAll}</div>
      ) : filtered.length === 0 ? (
        <div className="surface-card empty">بخشی با این فیلترها پیدا نشد.</div>
      ) : (
        <div className="surface-card overflow-hidden p-0">
          <VirtualChunkTable
            rows={filtered}
            emptyAll={emptyAll}
            emptyFiltered="بخشی با این فیلترها پیدا نشد."
            resetToken={resetToken}
          />
        </div>
      )}
    </div>
  )
}
