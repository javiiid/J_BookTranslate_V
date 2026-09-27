import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useTheme } from '@/hooks/useTheme'

/**
 * The KALIMA mark.
 *
 * Two SVG files rather than one with `currentColor`, because the variants are
 * not inversions of each other: on the light theme the blue is the ink and the
 * cream is the paper, and on the dark theme the aqua becomes the ink while the
 * document turns into the pale object. A single file cannot express that.
 *
 * `useTheme` rather than reading the class off <html> directly, so the mark
 * swaps the instant the toggle is pressed instead of on the next unrelated
 * render.
 */
export function KalimaMark({ size = 34 }: { size?: number }) {
  const { theme } = useTheme()
  return (
    <img
      src={theme === 'dark' ? '/brand/kalima-mark-dark.svg' : '/brand/kalima-mark-light.svg'}
      alt=""
      width={size}
      height={size}
      className="flex-none"
      /* Decorative: the product name is right beside it in text, so announcing
         the image too would read the name twice. */
    />
  )
}

interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV: NavItem[] = [
  { to: '/', label: 'داشبورد', icon: '◧' },
  { to: '/workspace', label: 'افزودن کتاب', icon: '＋' },
  { to: '/jobs', label: 'پایش ترجمه', icon: '◷' },
  { to: '/library', label: 'کتابخانه', icon: '▣' },
  { to: '/reader', label: 'مطالعه', icon: '❐' },
  { to: '/account', label: 'پنل کاربری', icon: '◈' },
]

/**
 * The rail.
 *
 * It was a floating rounded card with a 20px radius, a gradient logo tile and a
 * hover colour on every item. The brief asks for a flat, geometric, technical
 * surface with no decorative gradient, so this is now a full-height column
 * separated by a single border: no shadow, no rounded outer shape, and the
 * active item is marked by an inset edge rather than a filled pill.
 *
 * In RTL the active edge belongs on the right, where the reading direction
 * starts. `insetInlineStart` handles that without a second rule.
 */
export function Sidebar() {
  return (
    <aside
      className="fixed inset-y-0 end-0 z-40 flex w-60 flex-col border-s bg-[var(--color-surface)] pe-4 ps-3"
      style={{ borderColor: 'var(--color-border)' }}
      aria-label="ناوبری اصلی"
    >
      <div
        className="flex items-center gap-[var(--spacing-3)] py-4 pe-1"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <KalimaMark size={34} />
        <span className="min-w-0">
          <strong className="block truncate text-[length:var(--text-small)] tracking-wide" style={{ color: 'var(--color-text-primary)' }}>
            KALIMA
          </strong>
          <small className="block text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
            Word by word, book by book
          </small>
        </span>
      </div>

      <nav className="grid gap-0.5 py-3">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className="relative flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2.5 text-[length:var(--text-label)] font-semibold"
            style={({ isActive }) => ({
              color: isActive ? 'var(--color-text-brand)' : 'var(--color-text-secondary)',
              background: isActive ? 'var(--color-primary-subtle)' : 'transparent',
              // An inset edge on the reading-start side, instead of a filled
              // pill or a gradient underline.
              boxShadow: isActive ? 'inset -2px 0 0 0 var(--color-primary)' : 'none',
            })}
          >
            <span className="w-4 flex-none text-center text-[length:var(--text-small)]" aria-hidden="true">
              {icon}
            </span>
            {label}
          </NavLink>
        ))}
      </nav>

      <p
        className="mt-auto pb-4 text-[length:var(--text-caption)] leading-5"
        style={{ color: 'var(--color-text-muted)' }}
      >
        رابط React روی همان API پایتون.
        <br />
        بک‌اند دست‌نخورده است.
      </p>
    </aside>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh" style={{ background: 'var(--color-background)' }}>
      <Sidebar />
      {/* end-4 rather than a fixed px value, so the gutter survives RTL. */}
      <div className="me-60 min-h-dvh pe-6">{children}</div>
    </div>
  )
}
