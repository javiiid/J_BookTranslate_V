import { LANGUAGE_KEY, type Language } from './lang.ts'

function stored(): Language {
  try {
    return localStorage.getItem(LANGUAGE_KEY) === 'en' ? 'en' : 'fa'
  } catch {
    return 'fa'
  }
}

export function storedLanguage(): Language {
  return stored()
}

export function storeLanguage(lang: Language): void {
  try {
    localStorage.setItem(LANGUAGE_KEY, lang)
  } catch {
    // Private-mode storage failure must not break the toggle in memory.
  }
}

/** Applies the language before first paint to avoid an RTL flash on load. */
export function applyStoredLanguage(): Language {
  const lang = stored()
  document.documentElement.lang = lang
  document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr'
  return lang
}
