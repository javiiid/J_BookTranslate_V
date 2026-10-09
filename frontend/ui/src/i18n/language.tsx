import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { en } from './en.ts'
import { fa } from './fa.ts'
import { setLocale } from '../lib/locale.ts'
import { storeLanguage, storedLanguage } from './state.ts'
import type { Language } from './lang.ts'
import { LanguageContext, type LanguageValue } from './context.ts'

const DICTS = { fa, en } as const

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => storedLanguage())
  const setLang = useCallback((next: Language) => {
    setLangState(next)
    storeLanguage(next)
    // The pure formatters in `lib/format.ts` cannot call this hook, so the
    // active language is mirrored into the module they read.
    setLocale(next)
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr'
    setLocale(lang)
  }, [lang])

  const value = useMemo<LanguageValue>(
    () => ({
      lang,
      dir: lang === 'fa' ? 'rtl' : 'ltr',
      t: (key, vars) => {
        let text: string = DICTS[lang][key] ?? fa[key]
        if (vars) {
          for (const [name, replacement] of Object.entries(vars)) {
            text = text.replaceAll(`{${name}}`, String(replacement))
          }
        }
        return text
      },
      setLang,
    }),
    [lang, setLang],
  )
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}
