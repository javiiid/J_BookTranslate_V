import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ChunkRow } from '@/lib/chunks'
import { toRow } from '@/lib/chunks'
import { badgeClass, fa, serverError, statusLabel } from '@/lib/format'
import { AssetsTab } from '@/components/monitor/AssetsTab'
import { ChunksTab } from '@/components/monitor/ChunksTab'
import { LogsTab } from '@/components/monitor/LogsTab'
import { OverviewTab } from '@/components/monitor/OverviewTab'
import { QaTab } from '@/components/monitor/QaTab'
import { useLanguage } from '@/i18n/useLanguage.ts'

type TabId = 'overview' | 'chunks' | 'qa' | 'logs' | 'assets'

type ActionName = 'stop' | 'resume' | 'cancel' | 'rescue'

function Toast({ message, tone, onDone }: { message: string; tone: 'ok' | 'error'; onDone: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, 5000)
    return () => window.clearTimeout(timer)
  }, [message, onDone])

  return (
    <div
      // `status` rather than `alert`: a success message should not interrupt a
      // screen reader mid-sentence.
      role="status"
      aria-live="polite"
      className={`toast ${tone === 'ok' ? 'toast-ok' : 'toast-error'}`}
    >
      {message}
    </div>
  )
}

/**
 * @param initialTab Which tab to open on. Defaults to the overview.
 *
 * Exists so a render or a test can open a specific tab. The tab was `useState`
 * with a hardcoded `'overview'` and no way in, so the chunk table -- the widest
 * surface in the app, and the one the width work was done on -- could not be
 * rendered outside a click, and a layout that is only ever seen after a click
 * is a layout that does not get looked at.
 */
export function JobDetailPage({ initialTab = 'overview' }: { initialTab?: TabId } = {}) {
  const { t, dir } = useLanguage()
  const { id = '' } = useParams()
  const client = useQueryClient()
  const [tab, setTab] = useState<TabId>(initialTab)
  const [pending, setPending] = useState<ActionName | null>(null)
  const [toast, setToast] = useState<{ message: string; tone: 'ok' | 'error' } | null>(null)

  const tabs: { id: TabId; label: string }[] = [
    { id: 'overview', label: t('monitor.tab.overview') },
    { id: 'chunks', label: t('monitor.tab.chunks') },
    { id: 'qa', label: t('monitor.tab.qa') },
    { id: 'logs', label: t('monitor.tab.logs') },
    { id: 'assets', label: t('monitor.tab.assets') },
  ]

  const actionLabels: Record<ActionName, string> = {
    stop: t('monitor.action.stop'),
    resume: t('monitor.action.resume'),
    cancel: t('monitor.action.cancel'),
    rescue: t('monitor.action.rescue'),
  }

  /** The two destructive actions need a confirmation with the real consequence
   *  spelled out, matching the Python `confirmAction` copy. */
  const confirm: Partial<Record<ActionName, { title: string; body: string }>> = {
    stop: { title: t('monitor.confirm.stopTitle'), body: t('monitor.confirm.stopBody') },
    cancel: { title: t('monitor.confirm.cancelTitle'), body: t('monitor.confirm.cancelBody') },
  }

  const toastText: Record<ActionName, string> = {
    stop: t('monitor.toast.stop'),
    resume: t('monitor.toast.resume'),
    cancel: t('monitor.toast.cancel'),
    rescue: t('monitor.toast.rescue'),
  }

  // A running job is polled; a finished one is not, so a completed book does
  // not keep hitting the API for the rest of the day.
  const job = useQuery({
    queryKey: ['job', id],
    queryFn: () => api.job(id),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'queued' || status === 'stopping' ? 2000 : false
    },
  })

  // Chunks are only fetched when the tab needs them: a 400-chunk book is a
  // large payload and most visits never open the tab.
  const chunks = useQuery({
    queryKey: ['job-chunks', id],
    queryFn: () => api.jobChunks(id),
    enabled: Boolean(id) && (tab === 'chunks' || tab === 'qa'),
    staleTime: 5000,
  })

  const logs = useQuery({
    queryKey: ['job-logs', id],
    queryFn: () => api.jobLogs(id),
    enabled: Boolean(id) && tab === 'logs',
    refetchInterval: (query) =>
      query.state.data === undefined || (job.data?.status ?? '') === 'running' ? 3000 : false,
  })

  const rows = useMemo<ChunkRow[]>(
    () => (chunks.data?.items ?? []).map(toRow),
    [chunks.data],
  )

  const action = useMutation({
    mutationFn: (name: ActionName) => api.jobAction(id, name),
    onMutate: (name) => setPending(name),
    onSettled: () => setPending(null),
    onSuccess: (data, name) => {
      setToast({ message: toastText[name], tone: 'ok' })
      // A stop or cancel changes both the job and its chunk list.
      void client.invalidateQueries({ queryKey: ['job', id] })
      void client.invalidateQueries({ queryKey: ['job-chunks', id] })
      if (name === 'rescue' && data.download) window.location.href = data.download
    },
    onError: (error) => {
      setToast({
        message: error instanceof Error ? serverError(error.message) : t('monitor.actionFailed'),
        tone: 'error',
      })
    },
  })

  const runAction = (name: ActionName) => {
    const entry = confirm[name]
    if (entry && !window.confirm(`${entry.title}\n\n${entry.body}`)) return
    action.mutate(name)
  }

  if (job.isPending) {
    return (
      <main className="page" dir={dir}>
        <div className="grid gap-[var(--spacing-4)]">
          <div className="skeleton" style={{ height: 76 }} />
          <div className="skeleton" style={{ height: 320 }} />
        </div>
      </main>
    )
  }

  if (job.isError) {
    return (
      <main className="page" dir={dir}>
        <div className="surface-card p-[var(--spacing-5)]">
          <h1 className="text-[length:var(--text-h2)] font-extrabold">{t('monitor.title')}</h1>
          <p role="alert" className="mt-[var(--spacing-3)] text-[length:var(--text-small)]" style={{ color: 'var(--color-error)' }}>
            {t('monitor.notFound')}
          </p>
          <div className="mt-[var(--spacing-4)] flex gap-2">
            <Link to="/" className="btn btn-secondary">
              {t('monitor.back')}
            </Link>
            <button type="button" className="btn btn-secondary" onClick={() => job.refetch()}>
              {t('monitor.retry')}
            </button>
          </div>
        </div>
      </main>
    )
  }

  const data = job.data
  const busy = pending !== null

  return (
    <main className="page" dir={dir}>
      <header className="mb-[var(--spacing-5)]">
        <Link
          to="/"
          className="text-[length:var(--text-caption)]"
          style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}
        >
          {t('monitor.back')}
        </Link>
        <div className="mt-[var(--spacing-2)] flex flex-wrap items-start justify-between gap-[var(--spacing-4)]">
          <div className="min-w-0">
            <h1 className="truncate text-[length:var(--text-h1)] font-extrabold tracking-tight">{data.filename}</h1>
            <p className="mt-[var(--spacing-1)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
              {[data.filetype, `${data.source_language} → ${data.target_language}`, data.model]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={badgeClass(data.status)}>
              {statusLabel(data.status)}
            </span>
            {data.can_stop ? (
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => runAction('stop')}>
                {actionLabels.stop}
              </button>
            ) : null}
            {data.can_resume ? (
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => runAction('resume')}>
                {actionLabels.resume}
              </button>
            ) : null}
            {data.can_cancel ? (
              <button type="button" className="btn btn-danger" disabled={busy} onClick={() => runAction('cancel')}>
                {actionLabels.cancel}
              </button>
            ) : null}
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => runAction('rescue')}>
              {actionLabels.rescue}
            </button>
          </div>
        </div>
      </header>

      <div role="tablist" aria-label={t('monitor.tablist')} className="tab-list mb-[var(--spacing-5)]">
        {tabs.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`tab-${entry.id}`}
            aria-selected={tab === entry.id}
            aria-controls={`panel-${entry.id}`}
            className="tab-btn"
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
            {entry.id === 'chunks' && chunks.data?.total ? (
              <span className="ms-1 text-[length:var(--text-caption)] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                {fa(chunks.data.total)}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {/* Only the selected panel is mounted, so a hidden tab cannot hold stale
          data or steal focus. */}
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'overview' ? <OverviewTab job={data} /> : null}
        {tab === 'chunks' ? (
          <ChunksTab
            items={chunks.data?.items}
            available={chunks.data?.available ?? false}
            isPending={chunks.isPending}
            isError={chunks.isError}
            onRetry={() => void chunks.refetch()}
          />
        ) : null}
        {tab === 'qa' ? <QaTab job={data} rows={rows} isPending={chunks.isPending} /> : null}
        {tab === 'logs' ? (
          <LogsTab
            events={logs.data?.items}
            isPending={logs.isPending}
            isError={logs.isError}
            onRetry={() => void logs.refetch()}
          />
        ) : null}
        {tab === 'assets' ? <AssetsTab job={data} /> : null}
      </div>

      {toast ? (
        <Toast message={toast.message} tone={toast.tone} onDone={() => setToast(null)} />
      ) : null}
    </main>
  )
}

