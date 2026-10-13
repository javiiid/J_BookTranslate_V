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

const KIND_FA: Record<string, string> = {
  glossary: 'واژه‌نامه',
  preset: 'سبک ترجمه',
  style: 'شیوه‌نگارش',
}

const SCOPE_FA: Record<string, string> = {
  'translate:write': 'نوشتن ترجمه',
  'jobs:read': 'خواندن کارها',
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
        {test.isPending ? 'در حال آزمودن…' : 'آزمون اتصال'}
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
            ? ` مدل «${result.selected_model}» در فهرست ارائه‌دهنده نیست.`
            : ''}
        </p>
      ) : null}

      {failed ? (
        <p id="provider-test-result" role="alert" className="alert alert-error">
          {test.error instanceof Error ? test.error.message : 'آزمون ناموفق بود.'}
        </p>
      ) : null}
    </div>
  )
}

function SetupPanel({ config }: { config: ProviderConfig | undefined }) {
  const hasKey = config?.has_api_key ?? false

  return (
    <Panel
      title="راه‌اندازی"
      id="setup-heading"
      note={
        hasKey
          ? 'این مقادیر از config/config.yaml خوانده می‌شوند. برای تغییرشان همان فایل را ویرایش کنید.'
          : undefined
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Readout label="آدرس سرویس" value={config?.base_url ?? '—'} />
        <Readout label="مدل پیش‌فرض" value={config?.default_model ?? '—'} />
        <Readout
          label="کلید API"
          value={hasKey ? 'ثبت شده' : 'ثبت نشده'}
        />
        <Readout
          label="هم‌روندی"
          value={config ? fa(config.max_concurrency) : '—'}
        />
      </div>

      {hasKey ? (
        <ProviderTest config={config} />
      ) : (
        <p className="alert alert-warning mt-4">
          کلید API ثبت نشده است. ترجمه کار نخواهد کرد تا در{' '}
          <code>config/config.yaml</code> تنظیم شود.
        </p>
      )}
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Your work                                                           */
/* ------------------------------------------------------------------ */

function WorkPanel({ portal }: { portal: AccountPortal }) {
  const { counts, account, plan } = portal.overview
  const done = counts.completed_jobs
  const total = counts.jobs
  const ratio = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <Panel title="کار شما" id="work-heading">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Count label="کتاب‌ها" value={counts.books} />
        <Count label="کارها" value={total} />
        <Count label="تکمیل‌شده" value={done} />
        <Count label="واژه‌نامه‌ها" value={counts.glossaries} />
      </div>

      {/* Progress as a proportion, because "11 of 23" and "11 of 500" mean very
          different things and two bare numbers do not say which one you have. */}
      {total > 0 ? (
        <div className="mt-4">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="data-label">پیشرفت</span>
            <span
              className="text-[length:var(--text-small)] tabular-nums"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {fa(done)} از {fa(total)} · {fa(ratio)}٪
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={ratio}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="پیشرفت ترجمه"
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
          <dt className="data-label">نام نمایشی</dt>
          <dd className="text-[length:var(--text-body)]">
            {account.display_name || 'کاربر محلی'}
          </dd>
        </div>
        <div>
          <dt className="data-label">طرح</dt>
          <dd className="text-[length:var(--text-body)]">{plan.name_fa}</dd>
        </div>
        <div>
          <dt className="data-label">ساخته‌شده</dt>
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
  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: api.analytics,
    staleTime: 60_000,
  })

  // Never a silent `null`: an empty panel while loading or failed reads as
  // "there is no usage section", not as "it is still coming".
  if (analytics.isPending) {
    return (
      <Panel title="مصرف" id="usage-heading">
        <div className="skeleton" style={{ height: 72 }} />
      </Panel>
    )
  }

  if (analytics.isError) {
    return (
      <Panel title="مصرف" id="usage-heading">
        <p role="alert" className="alert alert-error">
          {analytics.error instanceof Error ? analytics.error.message : 'دریافت آمار مصرف ممکن نشد.'}
        </p>
      </Panel>
    )
  }

  const data = analytics.data
  // Unreachable while the query is enabled (pending and error return above),
  // kept so the type stays honest instead of asserting non-null.
  if (!data) return null

  return (
    <Panel title="مصرف" id="usage-heading">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Readout label="بخش‌های ترجمه‌شده" value={fa(data.completed_chunks)} />
        <Readout label="تلاش مجدد" value={fa(data.retries)} />
      </div>
      <p
        className="mt-3 text-[length:var(--text-caption)]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        توکن ورودی و خروجی و هزینهٔ تخمینی نمایش داده نمی‌شوند: لایهٔ ارائه‌دهنده
        هنوز مصرف توکن را ثبت نمی‌کند. نشان‌دادن صفر به‌جای این‌ها یعنی «رایگان
        بود»، که درست نیست؛ پس اصلاً نشان داده نمی‌شوند.
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
      <Panel title="امنیت" id="security-heading">
        <p className="empty">
          برای تغییر گذرواژه و مدیریت دستگاه‌ها اول{' '}
          <Link to="/login">وارد شوید</Link>.
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
      setFormError('گذرواژه باید حداقل ۸ نویسه باشد.')
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
      title="امنیت"
      id="security-heading"
      note="اگر کوکی‌تان لو رفته باشد، با عوض‌کردن گذرواژه یا خروج از همه دستگاه‌ها، نشست‌های دزدیده‌شده بلافاصله از کار می‌افتند."
    >
      <form
        className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
        onSubmit={submitPassword}
      >
        <label className="grid min-w-0 gap-1 text-[length:var(--text-label)]">
          گذرواژه فعلی
          <input
            type="password"
            autoComplete="current-password"
            className="input min-w-0"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1 text-[length:var(--text-label)]">
          گذرواژه جدید
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
          {change.isPending ? 'در حال تغییر…' : 'تغییر گذرواژه'}
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
            : 'تغییر گذرواژه ممکن نشد.'}
        </p>
      ) : null}
      {change.isSuccess ? (
        <p role="status" className="alert alert-success mt-3">
          گذرواژه عوض شد؛ همه دستگاه‌های دیگر خارج شدند.
        </p>
      ) : null}

      <h3 className="mt-5 text-[length:var(--text-small)] font-extrabold">
        دستگاه‌های واردشده
      </h3>
      {sessions.isPending ? (
        <div className="skeleton mt-2" style={{ height: 64 }} />
      ) : sessions.isError ? (
        <p role="alert" className="alert alert-error mt-2">
          دریافت فهرست دستگاه‌ها ممکن نشد.
        </p>
      ) : items.length === 0 ? (
        <p className="empty mt-2">نشستی ثبت نشده است.</p>
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
                  ساخته‌شده {faDate(item.created_at)} · آخرین فعالیت{' '}
                  {faAgo(item.last_seen_at) || faDate(item.last_seen_at)}
                </span>
              </div>
              {item.current ? (
                <span className="badge badge-success">این دستگاه</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => revokeOne.mutate(item.id)}
                  disabled={busy}
                >
                  باطل کردن
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
            ? 'در حال خروج…'
            : 'خروج از همه دستگاه‌های دیگر'}
        </button>
        {revokeAll.isSuccess ? (
          <p role="status" className="alert alert-success">
            {fa(revokeAll.data.closed)} دستگاه دیگر خارج شد.
          </p>
        ) : null}
        {revokeAll.isError ? (
          <p role="alert" className="alert alert-error">
            خروج از دستگاه‌ها ممکن نشد.
          </p>
        ) : null}
      </div>

      <h3 className="mt-5 text-[length:var(--text-small)] font-extrabold">
        رویدادهای ورود و خروج
      </h3>
      {events.isPending ? (
        <div className="skeleton mt-2" style={{ height: 64 }} />
      ) : events.isError ? (
        <p role="alert" className="alert alert-error mt-2">
          دریافت رویدادها ممکن نشد.
        </p>
      ) : log.length === 0 ? (
        <p className="empty mt-2">رویدادی ثبت نشده است.</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {log.slice(0, 20).map((entry) => (
            <li
              key={entry.id}
              className="surface-card flex min-w-0 flex-wrap items-center justify-between gap-3 p-3"
            >
              <div className="min-w-0">
                <strong className="block text-[length:var(--text-body)]">
                  {EVENT_FA[entry.event] ?? entry.event}
                </strong>
                <span
                  className="block text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {eventDetail(entry)}
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

const EVENT_FA: Record<string, string> = {
  login: 'ورود',
  logout: 'خروج',
  login_failed: 'ورود ناموفق',
  password_changed: 'تغییر گذرواژه',
  session_revoked: 'باطل‌کردن یک نشست',
  sessions_revoked: 'خروج از دستگاه‌های دیگر',
}

const METHOD_FA: Record<string, string> = {
  password: 'گذرواژه',
  'email-code': 'کد ایمیل',
  google: 'گوگل',
  apple: 'اپل',
}

/** Human line for the audit detail: a method, a closed-session count, or raw. */
function eventDetail(entry: AuthEvent): string {
  if (entry.event === 'login' || entry.event === 'login_failed') {
    return METHOD_FA[entry.detail] ?? entry.detail
  }
  if (entry.event === 'sessions_revoked' && /^\d+$/.test(entry.detail)) {
    return `${fa(Number(entry.detail))} نشست`
  }
  return entry.detail
}

/* ------------------------------------------------------------------ */
/* API keys                                                            */
/* ------------------------------------------------------------------ */

function KeysPanel({ keys }: { keys: PortalApiKey[] }) {
  const cache = useQueryClient()
  const revoke = useMutation({
    mutationFn: (id: number) => api.revokeApiKey(id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['portal'] }),
  })

  return (
    <Panel
      title="کلیدهای API"
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
        <p className="empty">کلیدی ساخته نشده است.</p>
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
                      .map((scope) => SCOPE_FA[scope] ?? scope)
                      .join('، ')}
                    {key.last_used_at
                      ? ` · آخرین استفاده ${faDate(key.last_used_at)}`
                      : ' · هنوز استفاده نشده'}
                  </span>
                </div>
                {revoked ? (
                  <span className="badge badge-neutral">باطل‌شده</span>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => revoke.mutate(key.id)}
                    disabled={revoke.isPending}
                  >
                    باطل کردن
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
  const cache = useQueryClient()
  const install = useMutation({
    mutationFn: (id: string) => api.installMarketplaceItem(id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['portal'] }),
  })

  if (items.length === 0) return null

  return (
    <Panel
      title="بسته‌های واژه‌نامه"
      id="packs-heading"
      note="نصب یک بسته، پروندهٔ آن را در همین نصب کپی می‌کند. چیزی خریده نمی‌شود؛ قیمت فقط واقعیتِ فهرست است و این محصول محلی خرید ندارد."
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
                  ★ {item.rating.toFixed(1)} · {fa(item.installs)} نصب
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
                  {KIND_FA[item.kind] ?? item.kind} · {item.language_pair} · $
                  {item.price_usd.toFixed(0)}
                </span>
                {done ? (
                  <span className="badge badge-success">نصب‌شده</span>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => install.mutate(item.id)}
                    disabled={install.isPending}
                  >
                    نصب
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
            : 'نصب انجام نشد.'}
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
  const { theme, setTheme, followsSystem } = useTheme()
  return (
    <Panel title="نمایش" id="appearance-heading">
      <fieldset className="grid gap-2 sm:grid-cols-2">
        <legend className="sr-only">حالت رنگی</legend>
        {(
          [
            ['light', 'روشن'],
            ['dark', 'تیره'],
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
            {theme === value ? <span className="text-[length:var(--text-caption)]">انتخاب‌شده</span> : null}
          </label>
        ))}
      </fieldset>
      <p
        className="mt-3 text-[length:var(--text-caption)]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {followsSystem
          ? 'فعلاً از تنظیم روشن/تاریک گوشی پیروی می‌کند. با انتخاب بالا، انتخاب خودتان ثبت می‌شود و دیگر با تغییر تنظیم گوشی عوض نمی‌شود.'
          : 'انتخاب شما ثبت شده و با تغییر تنظیم گوشی عوض نمی‌شود. برای بازگشت به حالت خودکار، در یکی از دو حالت بالا کلیک کنید و دوباره انتخاب کنید.'}
      </p>
    </Panel>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function AccountPage() {
  const portal = useQuery({ queryKey: ['portal'], queryFn: api.accountPortal })
  const config = useQuery({
    queryKey: ['provider-config'],
    queryFn: api.providerConfig,
    staleTime: 60_000,
  })

  if (portal.isPending) {
    return (
      <main className="page" dir="rtl">
        <div className="grid gap-4">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </main>
    )
  }

  if (portal.isError) {
    return (
      <main className="page" dir="rtl">
        <p role="alert" className="alert alert-error">
          دریافت اطلاعات حساب ممکن نشد.
        </p>
      </main>
    )
  }

  const data = portal.data
  const keys = (data.api_keys ?? []) as PortalApiKey[]
  const packs = (data.marketplace ?? []) as MarketplaceItem[]

  return (
    <main className="page" dir="rtl">
      <header className="mb-6">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
          پنل کاربری
        </h1>
        <p
          className="mt-1 text-[length:var(--text-small)]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          وضعیت نصب محلی، کارهای انجام‌شده و پیکربندی.
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
