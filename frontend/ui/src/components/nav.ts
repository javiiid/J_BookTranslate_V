/**
 * The navigation model, in one place.
 *
 * ## Why this is a `.ts` and not a `.tsx`
 *
 * It holds no JSX. The icon is a *name*, resolved to a component by
 * `NavIcon.tsx`, so the model is importable by `node --test` -- which cannot load
 * a `.tsx` at all, and therefore could not assert anything about the bar's
 * contents if the icons lived here. `tests/mobile-nav.test.ts` reads this file
 * directly; that is the only reason for the split, and it is a real one: a test
 * that has to reconstruct the data to check the data is checking its own copy.
 *
 * ## Why the icons are named and not drawn
 *
 * The rail used text characters -- `◧ ＋ ⇄ ◷ ▣ ❐ ◈`. A glyph is a font lookup
 * dressed up as an icon: it changes with whatever font is installed, it cannot
 * take a stroke weight, and it is a text character, so a screen reader reads it
 * out. `check-brand.mjs` cannot catch any of that. The replacements are 24px
 * strokes on `currentColor`, so they inherit the theme and scale.
 *
 * ## Why there are two lists
 *
 * The rail carries seven destinations. A bottom bar carries five, because six
 * already puts the label under 12px on a 393px screen -- and 12px is this
 * project's floor for Persian, where the letters join and the shapes are what
 * tell them apart.
 *
 * The split is declared here rather than in either component, so the desktop and
 * mobile navigations cannot disagree about what exists. The items left out of
 * the bar are not gone: each is one tap from a page that is in the bar.
 */

/** The icon set, as names. `NavIcon.tsx` is the only thing that maps these. */
export type NavIconName =
  | 'dashboard'
  | 'add'
  | 'convert'
  | 'monitor'
  | 'library'
  | 'reader'
  | 'account'
  | 'help'

export interface NavItem {
  to: string
  /**
   * The dictionary key for the label. Components render `t(key)` and fall
   * back to `label`/`short` below, which stay Persian: they are the default
   * language's own words, and `tests/mobile-nav.test.ts` reads them directly
   * to assert the bar's shape without rendering anything.
   */
  key: 'dashboard' | 'workspace' | 'convert' | 'jobs' | 'library' | 'reader' | 'account' | 'help'
  /** The full label, for the rail, where there is room for it. */
  label: string
  /**
   * The label for the bottom bar. A separate field rather than a truncation of
   * `label`, because `پایش ترجمه` cut to five characters is not a word -- it is a
   * different word, and a truncation has no way to know that.
   */
  short: string
  icon: NavIconName
  /**
   * Marks the primary action. In the bar it keeps a faint indicator at rest, so
   * the one thing worth doing stays visible without being selected.
   */
  primary?: boolean
}

/** Every destination, in rail order. */
export const NAV: readonly NavItem[] = [
  { to: '/', key: 'dashboard', label: 'داشبورد', short: 'داشبورد', icon: 'dashboard' },
  { to: '/workspace', key: 'workspace', label: 'افزودن کتاب', short: 'افزودن', icon: 'add', primary: true },
  { to: '/convert', key: 'convert', label: 'تبدیل فایل', short: 'تبدیل', icon: 'convert' },
  { to: '/jobs', key: 'jobs', label: 'پایش ترجمه', short: 'پایش', icon: 'monitor' },
  { to: '/library', key: 'library', label: 'کتابخانه', short: 'کتابخانه', icon: 'library' },
  { to: '/reader', key: 'reader', label: 'مطالعه', short: 'مطالعه', icon: 'reader' },
  { to: '/account', key: 'account', label: 'پنل کاربری', short: 'حساب', icon: 'account' },
  /* Help rides the rail only. The bottom bar stays five: a sixth label would
     drop under the 12px floor at 393px (`tests/mobile-nav.test.ts` holds it).
     On phones the center is one tap from the dashboard quick-access card. */
  { to: '/help', key: 'help', label: 'مرکز راهنما', short: 'راهنما', icon: 'help' },
]

/**
 * The bar's five, in reading order.
 *
 * `convert` and `reader` are not here. A bar is a summary, not a second rail:
 * what is missing has to be one tap from a page that is in the bar, and both
 * are -- conversion from the dashboard, the reader from the library and from any
 * finished job. Add a sixth only after measuring that a label still fits at
 * 393px, because the step below `--text-caption` does not exist in this project
 * at all.
 */
export const MOBILE_NAV: readonly NavItem[] = [
  NAV[0] as NavItem,
  NAV[4] as NavItem,
  NAV[1] as NavItem,
  NAV[3] as NavItem,
  NAV[6] as NavItem,
]

/** The item a list treats as its primary action, if one is marked. */
export function primaryItem(items: readonly NavItem[]): NavItem | undefined {
  return items.find((item) => item.primary)
}
