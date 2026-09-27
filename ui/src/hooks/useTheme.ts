import { useCallback, useEffect, useState } from 'react'

/** Storage key shared with the Python pages so the theme never resets while
 *  both UIs coexist.
 *
 *  The product was renamed to KALIMA and this key was deliberately not renamed.
 *  It is a preference already written into every existing user's
 *  localStorage under the old name; changing it would silently reset their
 *  theme to light, and since both UIs read the same key, changing it in one
 *  place would desynchronise them. 31 references across the two codebases
 *  depend on the exact string.
 *
 *  A rename is only safe as a migration: read the old key, write the new one.
 *  That is a deliberate task, not a rename. */
export const THEME_KEY = 'jbook-study-dark'

export type Theme = 'light' | 'dark'

function read(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === '1' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

/** Applies the theme before first paint to avoid a light flash on dark mode. */
export function applyStoredTheme(): Theme {
  const theme = read()
  document.documentElement.classList.toggle('dark', theme === 'dark')
  return theme
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try {
      localStorage.setItem(THEME_KEY, theme === 'dark' ? '1' : '0')
    } catch {
      // Private-mode storage failure must not break the toggle in memory.
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, setTheme, toggle }
}
