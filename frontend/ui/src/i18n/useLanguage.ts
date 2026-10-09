import { useContext } from 'react'
import { LanguageContext, type LanguageValue } from './context.ts'

export function useLanguage(): LanguageValue {
  return useContext(LanguageContext)
}
