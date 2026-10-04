import { useCallback, useEffect, useState } from 'react'

/** Storage key shared with the Python pages so the theme never resets while
 *  both UIs coexist.
 *
 * The product was renamed to KALIMA and this key was deliberately not renamed.
 * It is a preference already written into every existing user's
 * localStorage under the old name; changing it would silently reset their
 * theme to light, and since both UIs read the same key, changing it in one
 * place would desynchronise them. 31 references across the two codebases
 * depend on the exact string.
 *
 * A rename is only safe as a migration: read the old key, write the new one.
 * That is a deliberate task, not a rename. */
export const THEME_KEY = 'jbook-study-dark'

export type Theme = 'light' | 'dark'

/**
 * What the operating system asks for.
 *
 * `localStorage` is the wrong default on a phone. A reader who set their
 * handset to dark mode and then opened this app got a white page, because
 * "no stored preference" was read as "light". On a desktop that is a shrug; on
 * a phone it is the app looking broken at 2am.
 *
 * Wrapped because `matchMedia` is absent in some non-browser hosts, and a
 * missing API must not take the theme down.
 */
export function systemPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

/**
 * The stored choice, or `null` when the reader has never chosen.
 *
 * The distinction matters: `null` means "follow the system", while `'light'`
 * means "I picked light even though my phone is dark". Collapsing them — which
 * this did, by reading anything that was not `'1'` as light — throws away the
 * second kind of choice on every load.
 */
function stored(): Theme | null {
  try {
    const value = localStorage.getItem(THEME_KEY)
    return value === '1' ? 'dark' : value === '0' ? 'light' : null
  } catch {
    return null
  }
}

function resolve(): Theme {
  const choice = stored()
  return choice ?? (systemPrefersDark() ? 'dark' : 'light')
}

/** Applies the theme before first paint to avoid a light flash on dark mode. */
export function applyStoredTheme(): Theme {
  const theme = resolve()
  document.documentElement.classList.toggle('dark', theme === 'dark')
  return theme
}

export function useTheme() {
  const [choice, setChoice] = useState<Theme | null>(stored)
  // Derived rather than stored, so a system change is picked up without a
  // second state variable that could disagree with this one.
  const theme: Theme = choice ?? (systemPrefersDark() ? 'dark' : 'light')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  /* Follow the system while the reader has not chosen.
   *
   * The listener is only attached while `choice` is null. Once someone has
   * pressed the toggle the stored value wins, which is what they asked for —
   * and it is also what keeps this UI and the Python pages agreeing, since both
   * read the same key and neither can end up on a theme the other does not
   * know about. */
  useEffect(() => {
    if (choice !== null) return
    let query: MediaQueryList
    try {
      query = window.matchMedia('(prefers-color-scheme: dark)')
    } catch {
      return
    }
    const onChange = () => setChoice((current) => current)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [choice])

  const setTheme = useCallback((next: Theme) => {
    setChoice(next)
    try {
      localStorage.setItem(THEME_KEY, next === 'dark' ? '1' : '0')
    } catch {
      // Private-mode storage failure must not break the toggle in memory.
    }
  }, [])

  const toggle = useCallback(() => {
    setTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark')
  }, [setTheme])

  return { theme, setTheme, toggle, followsSystem: choice === null }
}
