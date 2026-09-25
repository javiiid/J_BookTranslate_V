import { Link } from 'react-router-dom'

const PENDING: { path: string; label: string; note: string }[] = [
  { path: '/jobs', label: 'پایش ترجمه', note: 'فاز ۲ — بعد از تأیید اسکلت' },
  { path: '/library', label: 'کتابخانه', note: 'فاز ۳' },
  { path: '/reader', label: 'مطالعه', note: 'فاز ۴' },
  { path: '/account', label: 'پنل کاربری', note: 'فاز ۵' },
]

export function PendingPage({ title }: { title: string }) {
  return (
    <main className="px-6 py-8" dir="rtl">
      <div className="surface-card p-8">
        <h1 className="text-2xl font-extrabold">{title}</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>
          این صفحه هنوز از رابط پایتون استفاده می‌کند. نسخهٔ React در فاز بعدی ساخته می‌شود.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center rounded-full px-5 py-2.5 text-sm font-bold text-white"
          style={{ background: 'var(--blue)' }}
        >
          بازگشت به داشبورد
        </Link>
      </div>
    </main>
  )
}

export function NotFoundPage() {
  return (
    <main className="px-6 py-8" dir="rtl">
      <div className="surface-card p-8">
        <h1 className="text-2xl font-extrabold">صفحه پیدا نشد</h1>
        <ul className="mt-6 grid gap-2">
          {PENDING.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className="flex items-center justify-between rounded-xl border p-3 text-sm"
                style={{ borderColor: 'var(--line)' }}
              >
                <span className="font-semibold">{item.label}</span>
                <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
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
