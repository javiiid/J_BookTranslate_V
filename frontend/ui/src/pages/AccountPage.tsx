import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type AccountPortal,
  type MarketplaceItem,
  type PortalApiKey,
  type ProviderConfig,
  type ProviderTestResult,
} from '@/lib/api'
import { fa, faDate, maskSecretLike } from '@/lib/format'

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
            ? ` مدل «${result.model}» در فهرست ارائه‌دهنده نیست.`
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

  const data = analytics.data
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

      <SetupPanel config={config.data} />
      <WorkPanel portal={data} />
      <UsagePanel />
      <KeysPanel keys={keys} />
      <PacksPanel items={packs} />
    </main>
  )
}
