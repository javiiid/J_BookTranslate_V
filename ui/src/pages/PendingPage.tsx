import { Link } from 'react-router-dom'

const PENDING: { path: string; label: string; note: string }[] = [
  { path: '/jobs', label: 'پایش ترجمه', note: 'فاز ۳' },
  { path: '/library', label: 'کتابخانه', note: 'فاز ۳' },
  { path: '/reader', label: 'مطالعه', note: 'فاز ۴' },
  { path: '/account', label: 'پنل کاربری', note: 'فاز ۵' },
]

export function PendingPage({ title }: { title: string }) {
  return (
    <main className="page" dir="rtl">
      <div className="surface-card p-8">
        <h1 className="text-[length:var(--text-h1)] font-extrabold">{title}</h1>
        <p
          className="mt-[var(--spacing-2)] text-[length:var(--text-body)]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          این صفحه هنوز از رابط پایتون استفاده می‌کند. نسخهٔ React در فاز بعدی ساخته می‌شود.
        </p>
        <Link to="/" className="btn btn-primary mt-6">
          بازگشت به داشبورد
        </Link>
      </div>
    </main>
  )
}

export function NotFoundPage() {
  return (
    <main className="page" dir="rtl">
      <div className="surface-card p-8">
        <h1 className="text-[length:var(--text-h1)] font-extrabold">صفحه پیدا نشد</h1>
        <p
          className="mt-[var(--spacing-2)] text-[length:var(--text-body)]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          این مسیر هنوز port نشده است. از یکی از موارد زیر ادامه دهید:
        </p>
        <ul className="mt-[var(--spacing-5)] grid gap-2">
          {PENDING.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className="flex items-center justify-between rounded-[var(--radius-control)] border p-[var(--spacing-3)] text-[length:var(--text-body)] transition-colors"
                style={{ borderColor: 'var(--color-border)' }}
                onMouseEnter={(event) => {
                  event.currentTarget.style.borderColor = 'var(--color-primary)'
                  event.currentTarget.style.background = 'var(--color-surface-elevated)'
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.borderColor = 'var(--color-border)'
                  event.currentTarget.style.background = 'transparent'
                }}
              >
                <span className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {item.label}
                </span>
                <span
                  className="text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {item.note}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </main>
  )
}
