import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { NAV } from './nav'
import { NavIcon } from './NavIcon'
import { MobileNav } from './MobileNav'

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

/**
 * The theme switch.
 *
 * It lives here, in the chrome that is on every page, rather than being copied
 * into individual pages. It used to appear on both the dashboard and the account
 * page, which meant two places to keep in step and no way to switch theme from
 * anywhere else -- the reader, the library and the workspace had no control at
 * all.
 */
export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      /* The accessible name is fixed and `aria-pressed` carries the state.
         The name used to flip with the theme as well, so a screen reader in
         dark mode heard "turn on light mode, pressed" -- a label and a state
         that contradict each other. The tooltip may still name the action. */
      aria-label="حالت تاریک"
      title={dark ? 'تغییر به حالت روشن' : 'تغییر به حالت تاریک'}
      className="btn-icon"
    >
      <ThemeIcon dark={dark} />
    </button>
  )
}

/**
 * Sun in the light theme, moon in the dark one: the icon shows the theme that
 * is on. That is what `aria-pressed` reports, so the picture and the state agree
 * (the reverse -- showing where the press goes -- put a sun on a button that
 * says "dark mode: on").
 *
 * Drawn on the same 24px / 1.75 stroke as `NavIcon`. The glyphs it replaces
 * (U+2600, U+25D0) are text characters, so each platform drew them from a
 * different font -- an emoji-style sun on phones, a hairline half-circle on
 * Windows -- and neither matched the rail's outline icons.
 */
function ThemeIcon({ dark }: { dark: boolean }) {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {!dark ? (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </>
      ) : (
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
      )}
    </svg>
  )
}

/**
 * The theme control, for the places that have a header of their own.
 *
 * The desktop rail carries one in its footer and `MobileNav` carries one in the
 * bar's chrome slot, so on every page at every width there is a way to reach
 * dark mode. `/account` states it as a preference too, so it is findable as one.
 */
export function ThemeToggleOnNarrow() {
  return <ThemeToggle />
}

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
 *
 * It is `hidden` below `lg`, where `MobileNav` takes over. Both are in the DOM
 * at every width and the inactive one is `display: none`, which is what a screen
 * reader and a keyboard user need: a hidden landmark is skipped, and a
 * `visibility`-hidden one is still focusable and announces itself.
 */
export function Sidebar() {
  return (
    <aside
      className="fixed inset-y-0 end-0 z-40 hidden w-60 flex-col border-s bg-[var(--color-surface)] pe-4 ps-3 lg:flex"
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
            <span className="flex flex-none items-center justify-center" aria-hidden="true">
              <NavIcon name={icon} size={18} />
            </span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* This footer carried a migration note ("React front end on the same
          Python API, backend untouched"). That is a message from the
          developer to the developer; to everyone else it was noise on every
          page, so the footer is the theme switch and nothing else. */}
      <div className="mt-auto flex items-center pb-3">
        <ThemeToggle />
      </div>
    </aside>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    /* No `min-h-dvh` on either div. `body` already owns the minimum height in
       tokens.css, and this stack had three of them: the body rule, this div and
       the content div. `dvh` is a *dynamic* unit -- it re-resolves when the
       mobile browser bar slides -- so three elements sized from it grew three
       times over, and the page became taller than its own content while you
       scrolled down it. That is the report: "I reach the end and there is more
       empty page below it."

       Growth is now content-driven, so the page is exactly as tall as what it
       holds. */
    <div style={{ background: 'var(--color-background)' }}>
      {/* Focus is moved by hand instead of following the `#content` hash, so
          the URL does not pick up a fragment on every skip. */}
      <a
        href="#content"
        className="btn btn-primary skip-link"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('content')?.focus()
        }}
      >
        پرش به محتوا
      </a>
      <Sidebar />
      <MobileNav />
      {/*
        The shell owns two things and no more: the offset for the rail, and the
        space the fixed bottom bar needs. The gutter is the page's own, via
        `.page` -- it used to be `pe-6` here, so the horizontal padding lived in
        this file while the vertical lived in each page, and only on one side.

        `lg:me-60` clears the rail and `lg:pb-0` gives the bar's space back once
        the bar is not rendered. Without it every desktop page carries dead
        space at the bottom for a bar that is not there.
      */}
      <div
        className="me-0 pb-[calc(var(--mobile-nav-height)+env(safe-area-inset-bottom,0px))] focus:outline-none lg:me-60 lg:pb-0"
        id="content"
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  )
}
