import { NavLink } from 'react-router-dom'
import { MOBILE_NAV } from './nav'
import type { StringKey } from '@/i18n/fa.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { NavIcon } from './NavIcon'
import { LanguageToggle, ThemeToggle } from './AppShell'

/**
 * The bottom bar for narrow screens.
 *
 * ## The shape it follows
 *
 * Five destinations, each an icon in a 56x32 rounded pill over a one-word label.
 * There are three looks, and none of them is told apart by colour alone:
 *
 *  - idle: no pill, a quiet ink, a medium-weight label;
 *  - selected: the pill (pale by day, a solid blue by night), the strong ink and
 *    a bold label;
 *  - the primary action: a solid pill at rest, navy by day and amber by night,
 *    so the one thing worth doing is findable without being on it. When it is
 *    also the current page it keeps that fill and gains a ring. It cannot swap
 *    to the selection pill the way the others do, because a swap is invisible
 *    wherever the two fills are close, and a ring is not.
 *
 * Weight is the second cue on purpose. Idle and selected labels were 1.39:1
 * apart in colour by day, which is no cue at all; 500 against 700 is one.
 *
 * ## What it deliberately does not do
 *
 * It does not float. The rail is a flat column separated by a single border, and
 * this is the same surface on the other edge -- no rounded outer shape, no
 * shadow, no gradient. A floating pill on mobile would make the phone layout
 * look like a different product from the desktop one, and the brief asks for a
 * flat, geometric surface. (The ring on a selected primary is `box-shadow` with
 * no blur: an outline, used because `outline` is the focus ring's job.)
 *
 * It is `fixed`, so `AppShell` reserves its height. A bar that covers the last
 * field of a form is worse than no bar.
 *
 * ## Why the labels are short
 *
 * `--text-caption` is 12px, this project's floor for Persian: the script joins,
 * and the shapes are what tell the letters apart, so 11px was reported as
 * unreadable and is not on the scale. Five items beside the theme switch on a
 * 393px screen leaves about 64px each, which holds one Persian word at 12px and
 * not two -- hence `short` being its own field on the model rather than a
 * truncation of `label`.
 *
 * The safe-area inset is honoured because on a notched phone the home indicator
 * sits exactly where the labels are.
 */
export function MobileNav() {
  const { t } = useLanguage()
  return (
    <nav
      aria-label={t('shell.mainNav')}
      /* `inset-x-0`, not `inset-inline-0`: the latter is not a utility, so it
         generated nothing and left a `fixed` bar with no width. */
      className="mobile-nav fixed inset-x-0 bottom-0 z-40 border-t lg:hidden"
      style={{
        background: 'var(--color-surface)',
        borderColor: 'var(--color-border)',
        /* The home indicator lives here on a notched phone, so the labels are
           lifted clear of it rather than sitting on top of it. */
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      <div className="flex w-full items-stretch">
        <ul className="flex flex-1 items-stretch" style={{ minHeight: 'var(--mobile-nav-height)' }}>
          {MOBILE_NAV.map(({ to, key, icon, primary: isPrimary }) => (
            <li key={to} className="flex min-w-0 flex-1">
              <NavLink
                to={to}
                /* The whole column is the target and it is as tall as the bar
                   (64px, over the 44px floor). It is the link, not the li, that
                   carries the height.

                   `-outline-offset-2` draws the focus ring inside the column.
                   The default ring sits 2px outside, which on the first, last
                   and bottom edge of a full-bleed bar is off the screen.

                   `group` so that pressing anywhere in the column presses the
                   pill, not only the pill itself. */
                className="group relative flex w-full touch-manipulation flex-col items-center justify-center gap-1 px-1 pt-2 [-webkit-tap-highlight-color:transparent] focus-visible:-outline-offset-2"
                style={{ minHeight: 'var(--mobile-nav-height)' }}
              >
                {({ isActive }) => {
                  const primary = isPrimary === true
                  /* Selected and the primary action share the strong ink, the
                     heavier stroke and the bold label. */
                  const strong = isActive || primary
                  return (
                    <>
                      <span
                        className="grid h-8 w-14 flex-none place-items-center rounded-full transition-[background-color,color,scale] duration-150 ease-[var(--ease-out)] group-active:scale-95"
                        style={{
                          background: primary
                            ? 'var(--color-nav-primary)'
                            : isActive
                              ? 'var(--color-nav-indicator)'
                              : 'transparent',
                          color: primary
                            ? 'var(--color-nav-primary-ink)'
                            : isActive
                              ? 'var(--color-nav-indicator-ink)'
                              : 'var(--color-nav-idle)',
                          /* The primary's "you are here". One pixel of the bar's
                             own surface, then two of the pill's colour. */
                          boxShadow:
                            primary && isActive
                              ? '0 0 0 1px var(--color-surface), 0 0 0 3px var(--color-nav-primary)'
                              : 'none',
                        }}
                      >
                        <NavIcon name={icon} size={22} strokeWidth={strong ? 2 : 1.75} />
                      </span>
                      <span
                        className={`whitespace-nowrap text-[length:var(--text-caption)] leading-[1.4] transition-colors duration-150 ease-[var(--ease-out)] ${
                          strong ? 'font-bold' : 'font-medium'
                        }`}
                        style={{
                          color: strong ? 'var(--color-nav-indicator-ink)' : 'var(--color-nav-idle)',
                        }}
                      >
                        {t(`nav.${key}.short` as StringKey)}
                      </span>
                    </>
                  )
                }}
              </NavLink>
            </li>
          ))}
        </ul>
        {/* The theme control, in the bar's chrome slot rather than as a sixth
            destination.

            It was unreachable on a phone before: the only copy lived in the
            rail's footer, and the rail is `hidden` below `lg`. A floating
            corner button was tried and rejected — it overlapped the dashboard's
            status pill and the job page's own header button.

            It is deliberately NOT in `MOBILE_NAV`: that list is five items
            because six puts the label under 12px at 393px, and 12px is this
            project's floor for Persian (`components/nav.ts`,
            `tests/mobile-nav.test.ts`). A theme switch is not a destination, so
            it costs no label — a 44px target at the reading-end, beside the
            labels, not under them. The hairline before it is drawn by
            `.mobile-nav > div > ul + div` in `tokens.css`. */}
        <div className="flex flex-none items-center ps-[var(--spacing-1)]">
          <span className="flex items-center gap-[var(--spacing-1)]">
            <ThemeToggle />
            <LanguageToggle />
          </span>
        </div>
      </div>
    </nav>
  )
}
