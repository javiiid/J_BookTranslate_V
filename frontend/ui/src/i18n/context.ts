import { createContext } from 'react'
import { fa, type StringKey } from './fa.ts'
import type { Direction, Language } from './lang.ts'

export interface LanguageValue {
  lang: Language
  dir: Direction
  /** `t('dashboard.read', { count: '۳' })` fills `{count}`. Values arrive
   *  pre-formatted (numbers through `fa()`), so this never formats. */
  t: (key: StringKey, vars?: Record<string, string | number>) => string
  setLang: (lang: Language) => void
}

/**
 * Alone in this file on purpose: `tests/fast-refresh.test.ts` fails any
 * component module that also exports a plain value, and the hook has to
 * live separately for the same reason. No function here, so neither rule
 * sees this file at all.
 */
export const LanguageContext = createContext<LanguageValue>({
  lang: 'fa',
  dir: 'rtl',
  t: (key) => fa[key],
  setLang: () => {},
})
