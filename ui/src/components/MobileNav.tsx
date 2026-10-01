import { NavLink } from 'react-router-dom'
import { MOBILE_NAV } from './nav'
import { NavIcon } from './NavIcon'

/**
 * The bottom bar for narrow screens.
 *
 * ## The shape it follows
 *
 * Five destinations, an icon in a filled circle for the selected one, and a
 * short accent rule under its label. The circle is the selection; the rule is
 * redundant on purpose, because a reader who cannot tell the fill from the
 * surface still has the rule.
 *
 * ## What it deliberately does not do
 *
 * It does not float. The rail is a flat column separated by a single border, and
 * this is the same surface on the other edge -- no rounded outer shape, no
 * shadow, no gradient. A floating pill on mobile would make the phone layout
 * look like a different product from the desktop one, and the brief asks for a
 * flat, geometric surface.
 *
 * It is `fixed`, so `AppShell` reserves its height. A bar that covers the last
 * field of a form is worse than no bar.
 *
 * ## Why the labels are short
 *
 * `--text-caption` is 12px, this project's floor for Persian: the script joins,
 * and the shapes are what tell the letters apart, so 11px was reported as
 * unreadable and is not on the scale. Five items on a 393px screen leaves about
 * 78px each, which holds one Persian word at 12px and not two -- hence `short`
 * being its own field on the model rather than a truncation of `label`.
 *
 * The safe-area inset is honoured because on a notched phone the home indicator
 * sits exactly where the labels are.
 */
export function MobileNav() {
  return (
    <nav
      aria-label="ناوبری اصلی"
      className="fixed inset-x-0 bottom-0 z-40 border-t lg:hidden"
      style={{
        background: 'var(--color-surface)',
        borderColor: 'var(--color-border)',
        /* The home indicator lives here on a notched phone, so the labels are
           lifted clear of it rather than sitting on top of it. */
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      <ul
        className="mx-auto flex max-w-lg items-stretch"
        style={{ minHeight: 'var(--mobile-nav-height)' }}
      >
        {MOBILE_NAV.map(({ to, short, icon, primary: isPrimary }) => (
          <li key={to} className="flex min-w-0 flex-1">
            <NavLink
              to={to}
              /* `min-h-14` is 56px, over the 44px floor, and it is on the link
                 rather than the li so the whole column is the target. */
              className="relative flex min-h-14 w-full flex-col items-center justify-center gap-1 px-1 pt-2"
            >
              {({ isActive }) => {
                /* The primary action keeps a wash at rest, so the one thing
                   worth doing is findable without being on it. It is
                   `--color-primary-subtle`, never the selection fill: the
                   selection fill is the aqua in the dark theme, and a muted
                   label on the aqua measures 1.30:1. Two unselected states that
                   are actually distinguishable is the whole point. */
                const atRest = isPrimary === true && !isActive
                return (
                  <>
                    <span
                      className="grid size-9 flex-none place-items-center rounded-full transition-colors duration-150"
                      style={{
                        background: isActive
                          ? 'var(--color-nav-indicator)'
                          : atRest
                            ? 'var(--color-primary-subtle)'
                            : 'transparent',
                        color: isActive
                          ? 'var(--color-nav-indicator-ink)'
                          : 'var(--color-text-muted)',
                      }}
                    >
                      <NavIcon name={icon} size={20} />
                    </span>
                    <span
                      className="truncate text-[length:var(--text-caption)] font-semibold leading-[1.4]"
                      style={{
                        color: isActive
                          ? 'var(--color-text-brand)'
                          : 'var(--color-text-muted)',
                      }}
                    >
                      {short}
                    </span>
                    {/* The rule under the selected label. Its width is set
                       rather than left to the content, so it does not resize
                       when the selection moves between a short and a long
                       label. */}
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-1/2 bottom-1 h-0.5 -translate-x-1/2 rounded-full transition-opacity duration-150"
                      style={{
                        width: '1.75rem',
                        background: 'var(--color-accent-strong)',
                        opacity: isActive ? 1 : 0,
                      }}
                    />
                  </>
                )
              }}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
