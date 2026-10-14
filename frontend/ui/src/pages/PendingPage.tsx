import { Link } from 'react-router-dom'

/** Where a lost visitor can go. Every entry is a mounted React route in
 *  `App.tsx` — never bare `/reader`, which names no book (books open at
 *  `/reader/:id` from the library, the dashboard and the monitor). */
const DESTINATIONS: { path: string; label: string; note: string }[] = [
  { path: '/', label: 'میز کار ترجمه', note: 'داشبورد' },
  { path: '/workspace', label: 'افزودن کتاب', note: 'شروع ترجمه' },
  { path: '/convert', label: 'تبدیل فایل', note: 'ابزار سند' },
  { path: '/jobs', label: 'پایش ترجمه', note: 'کارها' },
  { path: '/library', label: 'کتابخانه', note: 'کتاب‌ها' },
  { path: '/help', label: 'مرکز راهنما', note: 'راهنماها' },
  { path: '/account', label: 'پنل کاربری', note: 'حساب' },
]

export function NotFoundPage() {
  return (
    <main className="page" dir="rtl">
      <div className="surface-card p-8">
        <h1 className="text-[length:var(--text-h1)] font-extrabold">صفحه پیدا نشد</h1>
        <p
          className="mt-[var(--spacing-2)] text-[length:var(--text-body)]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          این مسیر وجود ندارد. از یکی از موارد زیر ادامه دهید:
        </p>
        <ul className="mt-[var(--spacing-5)] grid gap-2">
          {DESTINATIONS.map((item) => (
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
