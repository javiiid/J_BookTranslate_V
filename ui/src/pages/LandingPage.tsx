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
import { NavIcon } from '@/components/NavIcon'
import type { NavIconName } from '@/components/nav'

interface Capability {
  to: string
  title: string
  body: string
  /* The same icon the rail uses for the same destination, so a card and its
     nav entry read as one thing. */
  icon: NavIconName
}

const CAPABILITIES: Capability[] = [
  {
    to: '/workspace',
    title: 'افزودن کتاب',
    icon: 'add',
    body: 'EPUB یا PDF را بدهید. بارگذاری هیچ هزینه‌ای ندارد؛ اول روی چند نمونهٔ واقعی کتاب لحن و واژه‌نامه را می‌سنجید.',
  },
  {
    to: '/jobs',
    title: 'پایش ترجمه',
    icon: 'monitor',
    body: 'پیشرفت هر کار، بخش‌های ترجمه‌شده، و هر چیزی که نیاز به بازبینی دارد.',
  },
  {
    to: '/library',
    title: 'کتابخانه',
    icon: 'library',
    body: 'هر کتابی که افزوده‌اید، با وضعیت ترجمه و حجم و تاریخ آخرین تغییر.',
  },
  {
    /* Two cards, one destination, on purpose: the study surface opens from the
       library because each translated book carries its own reader path. Bare
       `/reader` is proxied to the Python page, and a card that promised a
       reader and landed on the handover notice was the broken link this
       replaced. */
    to: '/library',
    title: 'مطالعه',
    icon: 'reader',
    body: 'خواندن دوزبانه از کتابخانه؛ متن اصلی کنار ترجمه.',
  },
  {
    to: '/convert',
    title: 'تبدیل فایل',
    icon: 'convert',
    body: 'خروجی گرفتن به Word، PDF، مارک‌داون یا متن ساده.',
  },
  {
    to: '/account',
    title: 'پنل کاربری',
    icon: 'account',
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
          کتاب را بدهید، لحن و واژه‌نامه را روی چند نمونهٔ واقعی بسنجید، بعد کتاب
          کامل را با همان پروفایل قفل‌شده ترجمه کنید. بخش‌های تأییدشده دوباره
          هزینه نمی‌شوند.
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
        {/* Keyed on the title, not the destination: two cards may legitimately
            point at the same page -- the reader opens from the library, since
            bare `/reader` is proxied to Python -- and keying on `to` gave React
            two children with the same key, which it warns about loudly and
            resolves by dropping one of them. */}
        {CAPABILITIES.map(({ to, title, body, icon }) => (
          <Link
            key={title}
            to={to}
            className="surface-card card-link p-[var(--spacing-4)]"
          >
            <span className="flex items-center gap-[var(--spacing-2)]">
              <span
                className="flex flex-none items-center"
                style={{ color: 'var(--color-text-brand)' }}
              >
                <NavIcon name={icon} size={18} />
              </span>
              <strong className="text-[length:var(--text-body)]">{title}</strong>
            </span>
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
