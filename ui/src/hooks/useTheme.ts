import { useCallback, useEffect, useState } from 'react'

/** Storage key shared with the Python pages so the theme never resets while
 *  both UIs coexist. Do not rename without updating design-system/MASTER.md. */
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
