import { useMemo, useState } from 'react'
import type { JobChunk } from '@/lib/api'
import { type ChunkStateFilter, type ChunkRow, filterChunks, toRow } from '@/lib/chunks'
import { fa } from '@/lib/format'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { VirtualChunkTable } from './VirtualChunkTable'

export interface ChunksTabProps {
  items: JobChunk[] | undefined
  available: boolean
  isPending: boolean
  isError: boolean
  onRetry: () => void
}

export function ChunksTab({ items, available, isPending, isError, onRetry }: ChunksTabProps) {
  const { t } = useLanguage()
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

  const states: { value: ChunkStateFilter; label: string }[] = [
    { value: 'all', label: t('monitor.chunks.all') },
    { value: 'done', label: t('monitor.chunks.done') },
    { value: 'pending', label: t('monitor.chunks.pending') },
    { value: 'flagged', label: t('monitor.chunks.flagged') },
  ]

  const filtered = useMemo(
    () => filterChunks(rows, { query, state, flaggedOnly }),
    [rows, query, state, flaggedOnly],
  )

  if (isError) {
    return (
      <div className="surface-card p-[var(--spacing-5)]">
        <p role="alert" className="alert alert-error">
          {t('monitor.chunks.loadError')}
        </p>
        <button type="button" className="btn btn-secondary" onClick={onRetry} style={{ marginTop: 12 }}>
          {t('monitor.retry')}
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
    ? t('monitor.chunks.emptyNone')
    : t('monitor.chunks.emptyUnavailable')

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
          placeholder={t('monitor.chunks.searchPh')}
          aria-label={t('monitor.chunks.searchAria')}
          className="field min-w-0 flex-1 basis-[14rem]"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
        />
        <label className="flex items-center gap-2 text-[length:var(--text-label)]">
          <span style={{ color: 'var(--color-text-muted)' }}>{t('monitor.chunks.statusLabel')}</span>
          <select
            value={state}
            onChange={(event) => {
              setState(event.target.value as ChunkStateFilter)
              touch()
            }}
            aria-label={t('monitor.chunks.filterAria')}
            className="field"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
          >
            {states.map((option) => (
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
          {t('monitor.chunks.flaggedOnly')}
        </label>
        <span className="ms-auto text-[length:var(--text-label)] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
          {t('monitor.chunks.count', { n: fa(filtered.length) })}
        </span>
      </div>

      {rows.length === 0 ? (
        <div className="surface-card empty">{emptyAll}</div>
      ) : filtered.length === 0 ? (
        <div className="surface-card empty">{t('monitor.chunks.noneFiltered')}</div>
      ) : (
        <div className="surface-card overflow-hidden p-0">
          <VirtualChunkTable
            rows={filtered}
            emptyAll={emptyAll}
            emptyFiltered={t('monitor.chunks.noneFiltered')}
            resetToken={resetToken}
          />
        </div>
      )}
    </div>
  )
}
