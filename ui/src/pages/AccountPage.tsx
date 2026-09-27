import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fa, faDate } from '@/lib/format'
import { useTheme } from '@/hooks/useTheme'

/**
 * Account and provider settings.
 *
 * Ported from `app/account/page.py`, but only the parts that are actually
 * local-first. The portal endpoint also returns plans, an org and credit
 * balances for a hosted deployment; those are shown as read-only facts here
 * because there is nothing to buy in a local install, and pretending otherwise
 * would be a fake checkout button.
 */

const KIND_FA: Record<string, string> = {
  purchase: 'خرید',
  usage: 'مصرف',
  refund: 'بازگشت',
  credit: 'اعتبار',
  adjustment: 'اصلاح',
}

const STATUS_TONE: Record<string, string> = {
  paid: 'badge badge-success',
  settled: 'badge badge-success',
  pending: 'badge badge-warning',
  failed: 'badge badge-error',
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-card p-3">
      <span className="data-label">{label}</span>
      <strong className="data-value truncate" title={value}>
        {value}
      </strong>
    </div>
  )
}

export function AccountPage() {
  const { theme, toggle } = useTheme()
  const portal = useQuery({ queryKey: ['portal'], queryFn: api.accountPortal })
  const config = useQuery({ queryKey: ['provider-config'], queryFn: api.providerConfig, staleTime: 60_000 })
  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: api.analytics,
    staleTime: 60_000,
  })

  if (portal.isPending) {
    return (
      <main className="py-8" dir="rtl">
        <div className="grid gap-4">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </main>
    )
  }

  if (portal.isError) {
    return (
      <main className="py-8" dir="rtl">
        <p role="alert" className="alert alert-error">
          دریافت اطلاعات حساب ممکن نشد.
        </p>
      </main>
    )
  }

  const data = portal.data
  const { account, counts, transactions } = data.overview

  return (
    <main className="py-8" dir="rtl">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">پنل کاربری</h1>
          <p
            className="mt-1 text-[length:var(--text-small)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {account.display_name || 'کاربر محلی'} · ساخته‌شده {faDate(account.created_at)}
          </p>
        </div>
        <button
          type="button"
          onClick={toggle}
          aria-pressed={theme === 'dark'}
          aria-label="تغییر حالت روشن و تاریک"
          className="btn-icon"
        >
          <span aria-hidden="true">{theme === 'dark' ? '☀' : '◐'}</span>
        </button>
      </header>

      {/* ---- counts ---- */}
      <section className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="آمار">
        {(
          [
            ['کتاب‌ها', counts.books],
            ['کارها', counts.jobs],
            ['تکمیل‌شده', counts.completed_jobs],
            ['واژه‌نامه‌ها', counts.glossaries],
            ['حافظهٔ ترجمه', counts.memory_entries],
            ['کلیدهای API', counts.api_keys],
            ['سفارش‌های باز', counts.open_orders],
            ['اعتبار', account.credit_balance],
          ] as [string, number][]
        ).map(([label, value]) => (
          <div key={label} className="surface-card p-3">
            <span className="data-label">{label}</span>
            <strong className="data-value text-[length:var(--text-h2)] tabular-nums">{fa(value)}</strong>
          </div>
        ))}
      </section>

      {/* ---- provider ---- */}
      <section className="surface-card mb-6 p-5" aria-labelledby="provider-heading">
        <h2 id="provider-heading" className="mb-3 text-[length:var(--text-h3)] font-extrabold">
          ارائه‌دهنده
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="آدرس سرویس" value={config.data?.base_url ?? '—'} />
          <Field label="مدل پیش‌فرض" value={config.data?.default_model ?? '—'} />
          <Field
            label="کلید API"
            value={config.data?.has_api_key ? 'ثبت شده' : 'ثبت نشده'}
          />
          <Field
            label="هم‌روندی"
            value={config.data ? fa(config.data.max_concurrency) : '—'}
          />
        </div>
        {config.data?.has_api_key ? null : (
          <p className="alert alert-warning mt-4">
            کلید API ثبت نشده است. ترجمه کار نخواهد کرد تا در{' '}
            <code>config/config.yaml</code> تنظیم شود.
          </p>
        )}
      </section>

      {/* ---- usage ---- */}
      {analytics.data ? (
        <section className="surface-card mb-6 p-5" aria-labelledby="usage-heading">
          <h2 id="usage-heading" className="mb-3 text-[length:var(--text-h3)] font-extrabold">
            مصرف
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field
              label="بخش‌های ترجمه‌شده"
              value={fa(analytics.data.completed_chunks)}
            />
            <Field
              label="توکن ورودی"
              value={fa(analytics.data.input_tokens)}
            />
            <Field
              label="توکن خروجی"
              value={fa(analytics.data.output_tokens)}
            />
            <Field
              label="تلاش مجدد"
              value={fa(analytics.data.retries)}
            />
          </div>
          <p
            className="mt-3 text-[length:var(--text-caption)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            هزینهٔ تخمینی نمایش داده نمی‌شود: لایهٔ ارائه‌دهنده هنوز مصرف توکن را ثبت
            نمی‌کند و عددی که ساخته شود ساختگی خواهد بود.
          </p>
        </section>
      ) : null}

      {/* ---- transactions ---- */}
      <section className="surface-card p-5" aria-labelledby="tx-heading">
        <h2 id="tx-heading" className="mb-3 text-[length:var(--text-h3)] font-extrabold">
          تراکنش‌ها
        </h2>
        {transactions.length === 0 ? (
          <p className="empty">تراکنشی ثبت نشده است.</p>
        ) : (
          <div style={{ overflow: 'auto' }}>
            <table className="vtable" style={{ maxHeight: 'none' }}>
              <thead>
                <tr>
                  <th scope="col">نوع</th>
                  <th scope="col">مرجع</th>
                  <th scope="col">مبلغ</th>
                  <th scope="col">اعتبار</th>
                  <th scope="col">وضعیت</th>
                  <th scope="col">تاریخ</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => (
                  <tr key={transaction.id} style={{ height: 'auto' }}>
                    <td style={{ height: 'auto' }}>{KIND_FA[transaction.kind] ?? transaction.kind}</td>
                    <td style={{ height: 'auto' }} className="chunk-id">
                      {transaction.reference_id}
                    </td>
                    <td style={{ height: 'auto' }} className="tabular-nums">
                      {transaction.amount_usd ? `$${transaction.amount_usd.toFixed(2)}` : '—'}
                    </td>
                    <td style={{ height: 'auto' }} className="tabular-nums">
                      {fa(transaction.credits)}
                    </td>
                    <td style={{ height: 'auto' }}>
                      <span className={STATUS_TONE[transaction.status] ?? 'badge'}>
                        {transaction.status}
                      </span>
                    </td>
                    <td style={{ height: 'auto' }}>{faDate(transaction.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}
