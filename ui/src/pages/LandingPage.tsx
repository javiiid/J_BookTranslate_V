/**
 * The landing page, in React.
 *
 * ## Why this exists
 *
 * `/landing` was the one path the React router declared and the Python backend
 * also served -- 65KB of server-rendered HTML, no React on it. Vite's proxy ran
 * before its SPA fallback, so a visit to `/landing` left the app entirely, and
 * the same shadowing sat on `/library`, `/account` and `/workspace`. The router
 * here redirected `/landing` to `/` as a way of hiding that.
 *
 * With the proxy narrowed to `/api` and `/downloads` -- see `vite.config.ts` --
 * every path belongs to React, so this page has to exist rather than redirect.
 * It is a marketing surface, not product surface, which is why it gets one card
 * per capability and no live data.
 */
import { Link } from 'react-router-dom'
import { KalimaMark } from '@/components/AppShell'
import { ThemeToggle } from '@/components/AppShell'

interface Capability {
  to: string
  title: string
  body: string
}

const CAPABILITIES: Capability[] = [
  {
    to: '/workspace',
    title: 'افزودن کتاب',
    body: 'یک EPUB یا PDF بدهید؛ متن به بخش‌های قابل ترجمه شکسته می‌شود و هر بخش جدا ترجمه می‌شود.',
  },
  {
    to: '/jobs',
    title: 'پایش ترجمه',
    body: 'پیشرفت هر کار، بخش‌های ترجمه‌شده، و هر چیزی که نیاز به بازبینی دارد.',
  },
  {
    to: '/library',
    title: 'کتابخانه',
    body: 'هر کتابی که افزوده‌اید، با وضعیت ترجمه و حجم و تاریخ آخرین تغییر.',
  },
  {
    to: '/reader',
    title: 'مطالعه',
    body: 'خواندن دوزبانه؛ متن اصلی کنار ترجمه، با واژه‌نامه و یادداشت.',
  },
  {
    to: '/convert',
    title: 'تبدیل فایل',
    body: 'خروجی گرفتن به Word، PDF، مارک‌داون یا متن ساده.',
  },
  {
    to: '/account',
    title: 'پنل کاربری',
    body: 'کلید ارائه‌دهنده، مدل پیش‌فرض، و فضای آزاد.',
  },
]

export function LandingPage() {
  return (
    <main className="page" dir="rtl">
      <header className="mb-[var(--spacing-8)] flex items-center justify-between gap-[var(--spacing-3)]">
        <span className="flex items-center gap-[var(--spacing-3)]">
          <KalimaMark size={34} />
          <span>
            <strong className="block text-[length:var(--text-small)] tracking-wide">KALIMA</strong>
            <small
              className="block text-[length:var(--text-caption)]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Word by word, book by book
            </small>
          </span>
        </span>
        <ThemeToggle />
      </header>

      {/* The one thing worth doing, stated once. */}
      <section className="mb-[var(--spacing-8)] max-w-[46rem]">
        <h1 className="text-[length:var(--text-h1)] font-extrabold tracking-tight">
          هر کتابی را به فارسی برگردانید
        </h1>
        <p
          className="mt-[var(--spacing-3)] text-[length:var(--text-body)]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          کتاب را بدهید، ترجمه را ببینید، و کنار متن اصلی بخوانید. واژه‌نامه در طول کار یاد گرفته
          می‌شود و پیشنهادهایش را خودتان تأیید می‌کنید.
        </p>
        <div className="control-row mt-[var(--spacing-5)]">
          <Link to="/workspace" className="btn btn-primary">
            افزودن کتاب
          </Link>
          <Link to="/library" className="btn btn-secondary">
            کتابخانه
          </Link>
        </div>
      </section>

      <section aria-label="قابلیت‌ها" className="grid gap-[var(--spacing-3)] sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map(({ to, title, body }) => (
          <Link
            key={to}
            to={to}
            className="surface-card block p-[var(--spacing-4)] no-underline transition-colors"
          >
            <strong className="block text-[length:var(--text-body)]">{title}</strong>
            <span
              className="mt-[var(--spacing-2)] block text-[length:var(--text-small)]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {body}
            </span>
          </Link>
        ))}
      </section>
    </main>
  )
}
