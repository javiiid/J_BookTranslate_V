/**
 * The active-language corpus: same slugs in both languages, so a link
 * never breaks when the reader switches language.
 *
 * Non-component helpers live here (a `.ts` module) rather than beside
 * the dialog: a `.tsx` that exports values next to a component breaks
 * Fast Refresh (`tests/fast-refresh.test.ts` holds that rule).
 */
import type { HelpCategory, HelpCorpus, HelpResultKind } from '../lib/help.ts'
import { helpArticlesEn, helpFaqsEn, helpVideosEn } from './content.en.ts'
import { helpArticlesFa, helpFaqsFa, helpVideosFa } from './content.fa.ts'
import type { Language } from '../i18n/lang.ts'
import type { StringKey } from '../i18n/fa.ts'
import { useLanguage } from '../i18n/useLanguage.ts'

export function helpCorpus(lang: Language): HelpCorpus {
  if (lang === 'en') return { articles: helpArticlesEn, faqs: helpFaqsEn, videos: helpVideosEn }
  return { articles: helpArticlesFa, faqs: helpFaqsFa, videos: helpVideosFa }
}

export function useHelpCorpus(): { corpus: HelpCorpus; lang: Language } {
  const { lang } = useLanguage()
  return { corpus: helpCorpus(lang), lang }
}

/** The four hub cards. Slugs must exist in both locales. */
export const HELP_SUGGESTED_SLUGS: readonly string[] = [
  'first-translation',
  'stop-resume',
  'glossary-workflow',
  'connection-errors',
]

export function categoryLabel(t: (key: StringKey) => string, category: HelpCategory): string {
  return t(`help.cat.${category}` as StringKey)
}

/** Where a search result goes. Articles and FAQs stay in-app. */
export function helpResultPath(result: {
  kind: HelpResultKind
  ref: string
  category: HelpCategory
}): string {
  if (result.kind === 'article') return `/help/articles/${result.ref}`
  return `/help?faq=${encodeURIComponent(result.ref)}&cat=${result.category}`
}
