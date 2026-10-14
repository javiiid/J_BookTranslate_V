import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  ApiError,
  type AccountPortal,
  type MarketplaceItem,
  type PortalApiKey,
  type ProviderConfig,
  type ProviderTestResult,
} from '@/lib/api'
import { validPassword, type AuthEvent, type AuthSession } from '@/lib/auth.ts'
import { fa, faAgo, faDate, maskSecretLike } from '@/lib/format'
import { useTheme } from '@/hooks/useTheme'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { StringKey } from '@/i18n/fa.ts'

/**
 * Account and settings.
 *
 * ## What this page is for
 *
 * The earlier version of this page was shaped like a hosted SaaS console: a plan
 * card, credit balances, a table of transactions. In a local install none of that
 * is real. The transactions table showed eight orders, all `pending`, for things
 * that were never bought, with no checkout anywhere in the product -- and the
 * usage section showed four numbers that were all `0`, because the provider layer
 * does not record token usage. That teaches a reader to distrust the page.
 *
 * So it now answers the three questions a local single-user install actually
 * raises:
 *
 *   1. Is my setup working?      -> Setup, and a real connectivity test
 *   2. What have I done?         -> Your work
 *   3. What have I configured?   -> Keys, and installed glossary packs
 *
 * ## What was removed, and why
 *
 * - **Transactions.** Eight permanently-pending orders for a checkout that does
 *   not exist. Not shown: a table that never changes is noise.
 * - **Plans and credit packages.** Real catalogue data, but buying is not
 *   something this product can do, so listing prices next to a local install is
 *   misleading. The active plan is still shown, as a fact.
 * - **Four zero-valued usage fields.** Replaced by the one number that is real,
 *   plus a note saying why the others are absent rather than zero.
 *
 * ## What is new
 *
 * - **A provider test that actually calls the provider.** `has_api_key: true` is
 *   a claim about a config file; a completed test is a fact. It also reports
 *   whether the selected model appears in the provider's own list, which is the
 *   failure that actually bites -- a valid key and a model the provider does not
 *   serve.
 * - **The chunking settings.** The semantic chunker's budget and context window
 *   are decisions the user makes, and they used to live only in a YAML file.
 * - **Installed glossary packs.** `marketplace` returns eight real, installable
 *   glossaries. In a local install installing one copies a file; it is not a
 *   purchase, and the price is shown as a fact without offering to charge.
 * - **API keys, masked.** See `maskSecretLike` in `lib/format.ts`.
 * - **Security.** Change-password (proves the current one, kills other
 *   sessions), signed-in devices with last activity and per-session revoke,
 *   revoke-all, and the login/logout audit trail — the leaked-cookie
 *   recovery path, surfaced here instead of only on /auth.
 */

/**
 * Dictionary keys for values the backend names in Latin. Unknown future
 * values render raw rather than blank — the same rule as `KIND_KEY` on the
 * library page, so the two cannot drift apart in behaviour.
 */
const KIND_KEY: Record<string, StringKey> = {
  glossary: 'account.packs.kind.glossary',
  preset: 'account.packs.kind.preset',
  style: 'account.packs.kind.style',
}

const kindLabel = (t: (key: StringKey) => string, kind: string): string => {
  const key = KIND_KEY[kind]
  return key ? t(key) : kind
}

const SCOPE_KEY: Record<string, StringKey> = {
  'translate:write': 'account.keys.scope.translate_write',
  'jobs:read': 'account.keys.scope.jobs_read',
}

const scopeLabel = (t: (key: StringKey) => string, scope: string): string => {
  const key = SCOPE_KEY[scope]
  return key ? t(key) : scope
}

const EVENT_KEY: Record<string, StringKey> = {
  login: 'account.security.event.login',
  logout: 'account.security.event.logout',
  login_failed: 'account.security.event.login_failed',
  password_changed: 'account.security.event.password_changed',
  session_revoked: 'account.security.event.session_revoked',
  sessions_revoked: 'account.security.event.sessions_revoked',
}

const METHOD_KEY: Record<string, StringKey> = {
  password: 'account.security.method.password',
  'email-code': 'account.security.method.email-code',
  google: 'account.security.method.google',
  apple: 'account.security.method.apple',
}

const eventLabel = (t: (key: StringKey) => string, event: string): string => {
  const key = EVENT_KEY[event]
  return key ? t(key) : event
}

/** Human line for the audit detail: a method, a closed-session count, or raw. */
function eventDetail(
  t: (key: StringKey, vars?: Record<string, string | number>) => string,
  entry: AuthEvent,
): string {
  if (entry.event === 'login' || entry.event === 'login_failed') {
    const key = METHOD_KEY[entry.detail]
    return key ? t(key) : entry.detail
  }
  if (entry.event === 'sessions_revoked' && /^\d+$/.test(entry.detail)) {
    return t('account.security.sessionsCount', { count: fa(Number(entry.detail)) })
  }
  return entry.detail
}

/* ------------------------------------------------------------------ */
/* Small pieces                                                        */
/* ------------------------------------------------------------------ */

function Panel({
  title,
  id,
  action,
  children,
  note,
}: {
  title: string
  id: string
  action?: React.ReactNode | undefined
  children: React.ReactNode
  /* `| undefined` explicitly, because this project compiles with
     exactOptionalPropertyTypes: true -- which means passing `note={maybeUndefined}`
     is an error unless the prop admits undefined on purpose. */
  note?: string | undefined
}) {
  return (
    <section className="surface-card mb-5 p-5" aria-labelledby={id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="text-[length:var(--text-h3)] font-extrabold">
          {title}
        </h2>
        {action}
      </div>
      {children}
      {note ? (
        <p
          className="mt-3 text-[length:var(--text-caption)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {note}
        </p>
      ) : null}
    </section>
  )
}

function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-card p-3">
      <span className="data-label">{label}</span>
      {/* `break-all` rather than truncate: a base URL or a token prefix that
          gets ellipsised is worse than one that wraps, because the reader cannot
          tell how much is missing. */}
      <strong className="data-value break-all" title={value}>
        {value}
      </strong>
    </div>
  )
}

/** A labelled count. Zero is shown, but muted, so a row of them reads as a row. */
function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="surface-card p-3">
      <span className="data-label">{label}</span>
      <strong
        className="data-value text-[length:var(--text-h2)] tabular-nums"
        style={value === 0 ? { color: 'var(--color-text-muted)' } : undefined}
      >
        {fa(value)}
      </strong>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Setup                                                               */
/* ------------------------------------------------------------------ */

function ProviderTest({ config }: { config: ProviderConfig | undefined }) {
  const { t } = useLanguage()
  const test = useMutation<ProviderTestResult>({
    mutationFn: () => api.testProvider(),
  })

  const result = test.data
  const failed = test.isError

  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => test.mutate()}
        disabled={test.isPending || !config?.has_api_key}
        aria-describedby="provider-test-result"
      >
        {test.isPending ? t('account.test.running') : t('account.test.run')}
      </button>

      {test.isPending ? (
        <span className="skeleton h-5 w-40" aria-hidden="true" />
      ) : null}

      {result && !failed ? (
        <p
          id="provider-test-result"
          role="status"
          className={result.model_available === false ? 'alert alert-warning' : 'alert alert-success'}
        >
          {result.message}
          {result.model_available === false
            ? t('account.test.modelMissing', { model: result.selected_model })
            : ''}
        </p>
      ) : null}

      {failed ? (
        <p id="provider-test-result" role="alert" className="alert alert-error">
          {test.error instanceof Error ? test.error.message : t('account.test.failed')}
        </p>
      ) : null}
    </div>
  )
}

function SetupPanel({ config }: { config: ProviderConfig | undefined }) {
  const { t } = useLanguage()
  const hasKey = config?.has_api_key ?? false

  return (
    <Panel
      title={t('account.setup.title')}
      id="setup-heading"
      note={
        hasKey
          ? t('account.setup.note')
          : undefined
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Readout label={t('account.setup.baseUrl')} value={config?.base_url ?? '—'} />
        <Readout label={t('account.setup.model')} value={config?.default_model ?? '—'} />
        <Readout
          label={t('account.setup.apiKey')}
          value={hasKey ? t('account.setup.keySet') : t('account.setup.keyUnset')}
        />
        <Readout
          label={t('account.setup.concurrency')}
          value={config ? fa(config.max_concurrency) : '—'}
        />
      </div>

      {hasKey ? (
        <ProviderTest config={config} />
      ) : (
        <p className="alert alert-warning mt-4">
          {t('account.setup.noKey', { file: 'config/config.yaml' })}
        </p>
      )}
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Your work                                                           */
/* ------------------------------------------------------------------ */

function WorkPanel({ portal }: { portal: AccountPortal }) {
  const { t } = useLanguage()
  const { counts, account, plan } = portal.overview
  const done = counts.completed_jobs
  const total = counts.jobs
  const ratio = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <Panel title={t('account.work.title')} id="work-heading">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Count label={t('account.work.books')} value={counts.books} />
        <Count label={t('account.work.jobs')} value={total} />
        <Count label={t('account.work.done')} value={done} />
        <Count label={t('account.work.glossaries')} value={counts.glossaries} />
      </div>

      {/* Progress as a proportion, because "11 of 23" and "11 of 500" mean very
          different things and two bare numbers do not say which one you have. */}
      {total > 0 ? (
        <div className="mt-4">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="data-label">{t('account.work.progress')}</span>
            <span
              className="text-[length:var(--text-small)] tabular-nums"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {t('account.work.progressLine', { done: fa(done), total: fa(total), ratio: fa(ratio) })}
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={ratio}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t('account.work.progressAria')}
            className="h-1.5 w-full overflow-hidden rounded-full"
            style={{ background: 'var(--color-surface-sunken)' }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${ratio}%`,
                background: 'var(--color-primary)',
              }}
            />
          </div>
        </div>
      ) : null}

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <div>
          <dt className="data-label">{t('account.work.displayName')}</dt>
          <dd className="text-[length:var(--text-body)]">
            {account.display_name || t('account.work.localUser')}
          </dd>
        </div>
        <div>
          <dt className="data-label">{t('account.work.plan')}</dt>
          <dd className="text-[length:var(--text-body)]">{plan.name_fa}</dd>
        </div>
        <div>
          <dt className="data-label">{t('account.work.created')}</dt>
          <dd className="text-[length:var(--text-body)]">{faDate(account.created_at)}</dd>
        </div>
      </dl>
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Usage                                                              */
/* ------------------------------------------------------------------ */

function UsagePanel() {
  const { t } = useLanguage()
  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: api.analytics,
    staleTime: 60_000,
  })

  // Never a silent `null`: an empty panel while loading or failed reads as
  // "there is no usage section", not as "it is still coming".
  if (analytics.isPending) {
    return (
      <Panel title={t('account.usage.title')} id="usage-heading">
        <div className="skeleton" style={{ height: 72 }} />
      </Panel>
    )
  }

  if (analytics.isError) {
    return (
      <Panel title={t('account.usage.title')} id="usage-heading">
        <p role="alert" className="alert alert-error">
          {analytics.error instanceof Error ? analytics.error.message : t('account.usage.failed')}
        </p>
      </Panel>
    )
  }

  const data = analytics.data
  // Unreachable while the query is enabled (pending and error return above),
  // kept so the type stays honest instead of asserting non-null.
  if (!data) return null

  return (
    <Panel title={t('account.usage.title')} id="usage-heading">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Readout label={t('account.usage.chunks')} value={fa(data.completed_chunks)} />
        <Readout label={t('account.usage.retries')} value={fa(data.retries)} />
      </div>
      <p
        className="mt-3 text-[length:var(--text-caption)]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {t('account.usage.note')}
      </p>
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Security                                                            */
/* ------------------------------------------------------------------ */

/**
 * Leaked-cookie recovery path, on /account where people look for it.
 *
 * The backend already owns the truth (`app/auth/service.py`: change-password
 * proves the current one and kills other sessions, revoke-all keeps only the
 * caller, per-session revoke by id prefix) and /auth already surfaces it —
 * but nobody hunts for account recovery on the login page. So it lives here
 * too: change the password, see the signed-in devices, leave them all.
 */
function SecurityPanel() {
  const { t } = useLanguage()
  const cache = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const sessions = useQuery({
    queryKey: ['sessions'],
    queryFn: api.authSessions,
    staleTime: 30_000,
    retry: false,
  })
  const events = useQuery({
    queryKey: ['auth-events'],
    queryFn: api.authEvents,
    staleTime: 30_000,
    retry: false,
  })

  function refreshSecurity(): void {
    void cache.invalidateQueries({ queryKey: ['sessions'] })
    void cache.invalidateQueries({ queryKey: ['auth-events'] })
  }

  const change = useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.authChangePassword(body),
    onSuccess: () => {
      setCurrentPassword('')
      setNewPassword('')
      setFormError(null)
      refreshSecurity()
    },
  })

  const revokeOne = useMutation({
    mutationFn: (id: string) => api.authRevokeSession({ session_id: id }),
    onSuccess: () => refreshSecurity(),
  })

  const revokeAll = useMutation({
    mutationFn: () => api.authRevokeAll(),
    onSuccess: () => refreshSecurity(),
  })

  /* The portal itself loads without a login, so a visitor meets this panel
     logged out: offer the login, not an error box. */
  if (sessions.error instanceof ApiError && sessions.error.status === 401) {
    return (
      <Panel title={t('account.security.title')} id="security-heading">
        <p className="empty">
          {t('account.security.loginPrompt')}{' '}
          <Link to="/login">{t('account.security.login')}</Link>.
        </p>
      </Panel>
    )
  }

  const items: AuthSession[] = sessions.data?.items ?? []
  const log: AuthEvent[] = events.data?.items ?? []
  const busy = change.isPending || revokeOne.isPending || revokeAll.isPending

  function submitPassword(event: React.FormEvent): void {
    event.preventDefault()
    if (change.isPending) return
    if (!validPassword(currentPassword) || !validPassword(newPassword)) {
      setFormError(t('account.security.weak'))
      return
    }
    setFormError(null)
    change.mutate({
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  return (
    <Panel
      title={t('account.security.title')}
      id="security-heading"
      note={t('account.security.note')}
    >
      <form
        className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
        onSubmit={submitPassword}
      >
        <label className="grid min-w-0 gap-1 text-[length:var(--text-label)]">
          {t('account.security.current')}
          <input
            type="password"
            autoComplete="current-password"
            className="input min-w-0"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1 text-[length:var(--text-label)]">
          {t('account.security.new')}
          <input
            type="password"
            autoComplete="new-password"
            className="input min-w-0"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="btn btn-secondary"
          disabled={change.isPending}
        >
          {change.isPending ? t('account.security.changing') : t('account.security.change')}
        </button>
      </form>

      {formError ? (
        <p role="alert" className="alert alert-error mt-3">
          {formError}
        </p>
      ) : null}
      {change.isError ? (
        <p role="alert" className="alert alert-error mt-3">
          {change.error instanceof Error
            ? change.error.message
            : t('account.security.changeFailed')}
        </p>
      ) : null}
      {change.isSuccess ? (
        <p role="status" className="alert alert-success mt-3">
          {t('account.security.changed')}
        </p>
      ) : null}

      <h3 className="mt-5 text-[length:var(--text-small)] font-extrabold">
        {t('account.security.devices')}
      </h3>
      {sessions.isPending ? (
        <div className="skeleton mt-2" style={{ height: 64 }} />
      ) : sessions.isError ? (
        <p role="alert" className="alert alert-error mt-2">
          {t('account.security.sessionsFailed')}
        </p>
      ) : items.length === 0 ? (
        <p className="empty mt-2">{t('account.security.noSessions')}</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="surface-card flex min-w-0 flex-wrap items-center justify-between gap-3 p-3"
            >
              <div className="min-w-0">
                {/* dir="ltr" on the truncating element itself: in an RTL line
                    the ellipsis would otherwise cut the identifying head. */}
                <span
                  dir="ltr"
                  className="chunk-id block truncate text-right"
                >
                  {item.id}…
                </span>
                <span
                  className="block text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {t('account.security.sessionLine', {
                    created: faDate(item.created_at),
                    seen: faAgo(item.last_seen_at) || faDate(item.last_seen_at),
                  })}
                </span>
              </div>
              {item.current ? (
                <span className="badge badge-success">{t('account.security.thisDevice')}</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => revokeOne.mutate(item.id)}
                  disabled={busy}
                >
                  {t('account.security.revoke')}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => revokeAll.mutate()}
          disabled={busy || items.filter((item) => !item.current).length === 0}
        >
          {revokeAll.isPending
            ? t('account.security.revoking')
            : t('account.security.revokeAll')}
        </button>
        {revokeAll.isSuccess ? (
          <p role="status" className="alert alert-success">
            {t('account.security.revokedAll', { count: fa(revokeAll.data.closed) })}
          </p>
        ) : null}
        {revokeAll.isError ? (
          <p role="alert" className="alert alert-error">
            {t('account.security.revokeFailed')}
          </p>
        ) : null}
      </div>

      <h3 className="mt-5 text-[length:var(--text-small)] font-extrabold">
        {t('account.security.events')}
      </h3>
      {events.isPending ? (
        <div className="skeleton mt-2" style={{ height: 64 }} />
      ) : events.isError ? (
        <p role="alert" className="alert alert-error mt-2">
          {t('account.security.eventsFailed')}
        </p>
      ) : log.length === 0 ? (
        <p className="empty mt-2">{t('account.security.noEvents')}</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {log.slice(0, 20).map((entry) => (
            <li
              key={entry.id}
              className="surface-card flex min-w-0 flex-wrap items-center justify-between gap-3 p-3"
            >
              <div className="min-w-0">
                <strong className="block text-[length:var(--text-body)]">
                  {eventLabel(t, entry.event)}
                </strong>
                <span
                  className="block text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {eventDetail(t, entry)}
                  {entry.ip ? ` · ${entry.ip}` : ''}
                  {' · '}
                  {faAgo(entry.created_at) || faDate(entry.created_at)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* API keys                                                            */
/* ------------------------------------------------------------------ */

function KeysPanel({ keys }: { keys: PortalApiKey[] }) {
  const { t } = useLanguage()
  const cache = useQueryClient()
  const revoke = useMutation({
    mutationFn: (id: number) => api.revokeApiKey(id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['portal'] }),
  })

  return (
    <Panel
      title={t('account.keys.title')}
      id="keys-heading"
      action={
        <span
          className="text-[length:var(--text-caption)] tabular-nums"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {fa(keys.length)}
        </span>
      }
    >
      {keys.length === 0 ? (
        <p className="empty">{t('account.keys.empty')}</p>
      ) : (
        <ul className="grid gap-2">
          {keys.map((key) => {
            const revoked = Boolean(key.revoked_at)
            return (
              <li
                key={key.id}
                className="surface-card flex flex-wrap items-center justify-between gap-3 p-3"
              >
                <div className="min-w-0">
                  {/* Masked. The endpoint returns this column verbatim and it is
                      user data, so anything shaped like a credential is not
                      printed. See `maskSecretLike`. */}
                  <strong className="block text-[length:var(--text-body)]">
                    {maskSecretLike(key.name)}
                  </strong>
                  <span
                    className="chunk-id block"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {key.token_prefix}… · {key.created_at.slice(0, 10)}
                  </span>
                  <span
                    className="block text-[length:var(--text-caption)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {key.scopes
                      .split(/\s+/)
                      .filter(Boolean)
                      .map((scope) => scopeLabel(t, scope))
                      .join(t('account.listSep'))}
                    {key.last_used_at
                      ? t('account.keys.lastUsed', { date: faDate(key.last_used_at) })
                      : t('account.keys.neverUsed')}
                  </span>
                </div>
                {revoked ? (
                  <span className="badge badge-neutral">{t('account.keys.revoked')}</span>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => revoke.mutate(key.id)}
                    disabled={revoke.isPending}
                  >
                    {t('account.keys.revoke')}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Glossary packs                                                      */
/* ------------------------------------------------------------------ */

function PacksPanel({ items }: { items: MarketplaceItem[] }) {
  const { t } = useLanguage()
  const cache = useQueryClient()
  const install = useMutation({
    mutationFn: (id: string) => api.installMarketplaceItem(id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['portal'] }),
  })

  if (items.length === 0) return null

  return (
    <Panel
      title={t('account.packs.title')}
      id="packs-heading"
      note={t('account.packs.note')}
    >
      <ul className="grid gap-2 md:grid-cols-2">
        {items.map((item) => {
          const done = Boolean(item.installed)
          return (
            <li key={item.id} className="surface-card flex flex-col gap-2 p-3">
              <div className="flex items-baseline justify-between gap-2">
                <strong className="text-[length:var(--text-body)]">
                  {item.title_fa}
                </strong>
                <span
                  className="text-[length:var(--text-caption)] tabular-nums"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  ★ {item.rating.toFixed(1)} · {t('account.packs.installs', { count: fa(item.installs) })}
                </span>
              </div>
              <p
                className="text-[length:var(--text-small)]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {item.description_fa}
              </p>
              <div className="mt-auto flex items-center justify-between gap-2 pt-1">
                <span
                  className="text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {kindLabel(t, item.kind)} · {item.language_pair} · $
                  {item.price_usd.toFixed(0)}
                </span>
                {done ? (
                  <span className="badge badge-success">{t('account.packs.installed')}</span>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => install.mutate(item.id)}
                    disabled={install.isPending}
                  >
                    {t('account.packs.install')}
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      {install.isError ? (
        <p role="alert" className="alert alert-error mt-3">
          {install.error instanceof Error
            ? install.error.message
            : t('account.packs.failed')}
        </p>
      ) : null}
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Appearance                                                          */
/* ------------------------------------------------------------------ */

/**
 * Where the theme lives as a *setting*.
 *
 * The rail's footer carries the same control on a desktop, and the shell has a
 * floating one for phones. Neither is a place someone looks for a preference,
 * so the preference is also stated here: what the theme is, where it came from,
 * and what will happen if the phone's system setting changes.
 */
function AppearancePanel() {
  const { t } = useLanguage()
  const { theme, setTheme, followsSystem } = useTheme()
  return (
    <Panel title={t('account.theme.title')} id="appearance-heading">
      <fieldset className="grid gap-2 sm:grid-cols-2">
        <legend className="sr-only">{t('account.theme.legend')}</legend>
        {(
          [
            ['light', t('account.theme.light')],
            ['dark', t('account.theme.dark')],
          ] as const
        ).map(([value, label]) => (
          <label
            key={value}
            className="flex items-center justify-between gap-3 rounded-[var(--radius-control)] border p-[var(--spacing-3)] text-[length:var(--text-label)]"
            style={{
              borderColor: theme === value ? 'var(--color-primary)' : 'var(--color-border)',
              background: theme === value ? 'var(--color-primary-subtle)' : 'transparent',
            }}
          >
            <span className="flex items-center gap-2">
              <input
                type="radio"
                name="theme"
                checked={theme === value}
                onChange={() => setTheme(value)}
              />
              {label}
            </span>
            {theme === value ? <span className="text-[length:var(--text-caption)]">{t('account.theme.selected')}</span> : null}
          </label>
        ))}
      </fieldset>
      <p
        className="mt-3 text-[length:var(--text-caption)]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {followsSystem
          ? t('account.theme.auto')
          : t('account.theme.manual')}
      </p>
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function AccountPage() {
  const { t, dir } = useLanguage()
  const portal = useQuery({ queryKey: ['portal'], queryFn: api.accountPortal })
  const config = useQuery({
    queryKey: ['provider-config'],
    queryFn: api.providerConfig,
    staleTime: 60_000,
  })

  if (portal.isPending) {
    return (
      <main className="page" dir={dir}>
        <div className="grid gap-4">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </main>
    )
  }

  if (portal.isError) {
    return (
      <main className="page" dir={dir}>
        <p role="alert" className="alert alert-error">
          {t('account.loadFailed')}
        </p>
      </main>
    )
  }

  const data = portal.data
  const keys = (data.api_keys ?? []) as PortalApiKey[]
  const packs = (data.marketplace ?? []) as MarketplaceItem[]

  return (
    <main className="page" dir={dir}>
      <header className="mb-6">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
          {t('account.title')}
        </h1>
        <p
          className="mt-1 text-[length:var(--text-small)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {t('account.subtitle')}
        </p>
      </header>

      <AppearancePanel />
      <SetupPanel config={config.data} />
      <WorkPanel portal={data} />
      <UsagePanel />
      <SecurityPanel />
      <KeysPanel keys={keys} />
      <PacksPanel items={packs} />
    </main>
  )
}
