/**
 * The help center's content model and search logic.
 *
 * Pure TypeScript, no JSX and no imports: `tests/help.test.ts` loads this
 * file with `node --test` (type-stripping, no resolution), so even a
 * same-directory relative import without an extension would fail the suite.
 * Keep it dependency-free.
 */

/** The seven topic buckets. The order here is the tab order on `/help`. */
export type HelpCategory =
  | 'getting-started'
  | 'translation-jobs'
  | 'library-reading'
  | 'glossary'
  | 'convert-export'
  | 'account-settings'
  | 'troubleshooting'

export const HELP_CATEGORIES: readonly HelpCategory[] = [
  'getting-started',
  'translation-jobs',
  'library-reading',
  'glossary',
  'convert-export',
  'account-settings',
  'troubleshooting',
]

/** A content block inside a section. Rendered, never edited in JSX. */
export type HelpBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'steps'; items: string[] }
  | { kind: 'note'; text: string }
  | { kind: 'warning'; text: string }
  | { kind: 'code'; code: string; label?: string | undefined }

export interface HelpSection {
  id: string
  heading: string
  blocks: HelpBlock[]
}

export interface HelpArticle {
  id: string
  /** URL-safe Latin slug: `/help/articles/:slug`. Never changes once linked. */
  slug: string
  title: string
  summary: string
  category: HelpCategory
  keywords: string[]
  sections: HelpSection[]
  relatedSlugs: string[]
  /** The real date this text was written and reviewed, `YYYY-MM-DD`. */
  reviewedAt: string
}

export interface HelpFaq {
  id: string
  question: string
  answer: string
  category: HelpCategory
  articleSlug?: string | undefined
}

export interface HelpVideo {
  id: string
  title: string
  description: string
  category: HelpCategory
  url: string
  /** Only these hosts may become an iframe; anything else is an outbound link. */
  provider: 'youtube' | 'link'
  duration?: string | undefined
  thumbnail?: string | undefined
  transcript?: string | undefined
}

/* ------------------------------------------------------------------ */
/* Persian-aware normalisation, scoped to help search only.            */
/*                                                                     */
/* This deliberately does NOT touch the translation glossary logic:    */
/* `src/lib/terms.ts` keeps ZWNJ and friends for term identity, while  */
/* search only needs "typed ي" to find "written ی".                    */
/* ------------------------------------------------------------------ */

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'

/** Fold a string for comparison: Arabic Yeh/Kaf, diacritics, ZWNJ, digits. */
export function normalizeHelpText(input: string): string {
  return input
    .toLowerCase()
    .replace(/ي/g, 'ی')
    .replace(/ك/g, 'ک')
    .replace(/ة/g, 'ه')
    // Combining marks (Arabic diacritics included) carry no search meaning.
    // A property escape, so no zero-width-joined sequence sits in a class.
    .replace(/\p{M}/gu, '')
    .replace(/\u200c|\u200d|\u200e|\u200f|\u00ad/g, ' ')
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)))
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Small, practical synonym pairs: `resume/ادامه`, `stop/توقف`,
 * `download/دانلود` and the dozen others a stuck user actually types.
 * Written pre-normalisation; matched post-normalisation.
 */
const HELP_SYNONYMS: ReadonlyArray<readonly string[]> = [
  ['resume', 'ادامه'],
  ['stop', 'توقف', 'متوقف'],
  ['cancel', 'لغو'],
  ['download', 'دانلود', 'دریافت'],
  ['upload', 'آپلود', 'بارگذاری'],
  ['glossary', 'واژه‌نامه', 'اصطلاح'],
  ['model', 'مدل'],
  ['error', 'خطا'],
  ['convert', 'تبدیل'],
  ['library', 'کتابخانه'],
  ['reader', 'مطالعه', 'خواندن'],
  ['calibration', 'کالیبراسیون', 'کارگاه'],
  ['tone', 'لحن'],
  ['sample', 'نمونه'],
  ['cost', 'هزینه'],
  ['font', 'فونت'],
  ['output', 'خروجی'],
  ['job', 'کار'],
  ['chunk', 'بخش'],
  ['quality', 'کیفیت'],
  ['account', 'حساب', 'پنل'],
  ['theme', 'تم', 'تاریک', 'روشن'],
  ['language', 'زبان'],
  ['book', 'کتاب'],
  ['translation', 'ترجمه'],
]

/**
 * Split a normalised query into per-token alternative lists.
 * AND semantics: every token group must match somewhere, so multi-word
 * queries narrow down instead of spraying.
 */
export function expandHelpTokens(normalizedQuery: string): string[][] {
  const tokens = normalizedQuery.split(' ').filter(Boolean)
  const alternatives = new Map<string, Set<string>>()
  for (const group of HELP_SYNONYMS) {
    const members = group.map(normalizeHelpText)
    if (!members.some((member) => normalizedQuery.includes(member))) continue
    const groupTokens = new Set(members.flatMap((m) => m.split(' ').filter(Boolean)))
    for (const token of tokens) {
      if (!groupTokens.has(token)) continue
      let set = alternatives.get(token)
      if (!set) {
        set = new Set<string>()
        alternatives.set(token, set)
      }
      for (const other of groupTokens) set.add(other)
    }
  }
  return tokens.map((token) => [token, ...(alternatives.get(token) ?? [])])
}

/* ------------------------------------------------------------------ */
/* Ranking                                                             */
/* ------------------------------------------------------------------ */

export type HelpResultKind = 'article' | 'faq' | 'video'

export interface HelpSearchResult {
  kind: HelpResultKind
  /** Article slug, FAQ id, or video id, depending on `kind`. */
  ref: string
  title: string
  summary: string
  category: HelpCategory
  score: number
}

export interface HelpCorpus {
  articles: HelpArticle[]
  faqs: HelpFaq[]
  videos: HelpVideo[]
}

/** All searchable text of an article, normalised once per search. */
function articleHaystack(article: HelpArticle): {
  title: string
  summary: string
  keywords: string
  body: string
} {
  const body = article.sections
    .map((section) =>
      [
        section.heading,
        ...section.blocks.map((block) => {
          switch (block.kind) {
            case 'paragraph':
            case 'note':
            case 'warning':
              return block.text
            case 'steps':
              return block.items.join(' ')
            case 'code':
              return block.code
          }
        }),
      ].join(' '),
    )
    .join(' ')
  return {
    title: normalizeHelpText(article.title),
    summary: normalizeHelpText(article.summary),
    keywords: normalizeHelpText(article.keywords.join(' ')),
    body: normalizeHelpText(body),
  }
}

/**
 * Rank one haystack against expanded tokens.
 * Weights, highest first: exact title > title word > keyword > FAQ
 * question > summary > video description > body text.
 * Returns 0 when any token group matches nowhere (AND semantics).
 */
function rankFields(
  tokens: string[][],
  fields: { title: string; question: string; keywords: string; summary: string; body: string },
): number {
  let score = 0
  for (const group of tokens) {
    let best = 0
    for (const token of group) {
      if (fields.title.includes(token)) best = Math.max(best, 40)
      else if (fields.question.includes(token)) best = Math.max(best, 40)
      else if (fields.keywords.includes(token)) best = Math.max(best, 30)
      else if (fields.summary.includes(token)) best = Math.max(best, 15)
      else if (fields.body.includes(token)) best = Math.max(best, 8)
    }
    if (best === 0) return 0
    score += best
  }
  return score
}

/**
 * One shared search for the page and the command dialog, so the two can
 * never disagree about what exists. `category` narrows; `limit` caps.
 * An empty query returns no results (the caller shows its hint instead),
 * so "no filter" is never confused with "no content".
 */
export function searchHelp(
  query: string,
  corpus: HelpCorpus,
  options?: { category?: HelpCategory | 'all' | undefined; limit?: number | undefined },
): HelpSearchResult[] {
  const normalized = normalizeHelpText(query)
  if (!normalized) return []
  const tokens = expandHelpTokens(normalized)
  const category = options?.category ?? 'all'
  const limit = options?.limit ?? 20
  const results: HelpSearchResult[] = []

  for (const article of corpus.articles) {
    if (category !== 'all' && article.category !== category) continue
    const hay = articleHaystack(article)
    let score = rankFields(tokens, { ...hay, question: '' })
    if (score > 0 && hay.title.includes(normalized)) score += 100
    if (score > 0) {
      results.push({
        kind: 'article',
        ref: article.slug,
        title: article.title,
        summary: article.summary,
        category: article.category,
        score,
      })
    }
  }

  for (const faq of corpus.faqs) {
    if (category !== 'all' && faq.category !== category) continue
    const score = rankFields(tokens, {
      title: '',
      question: normalizeHelpText(faq.question),
      keywords: '',
      summary: normalizeHelpText(faq.answer),
      body: '',
    })
    if (score > 0) {
      results.push({
        kind: 'faq',
        ref: faq.id,
        title: faq.question,
        summary: faq.answer,
        category: faq.category,
        score,
      })
    }
  }

  for (const video of corpus.videos) {
    if (category !== 'all' && video.category !== category) continue
    const score = rankFields(tokens, {
      title: normalizeHelpText(video.title),
      question: '',
      keywords: '',
      summary: normalizeHelpText(video.description),
      body: normalizeHelpText(video.transcript ?? ''),
    })
    if (score > 0) {
      results.push({
        kind: 'video',
        ref: video.id,
        title: video.title,
        summary: video.description,
        category: video.category,
        score,
      })
    }
  }

  results.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title, 'fa'))
  return results.slice(0, Math.max(0, limit))
}

/** Whole-word count over every block; ~180 wpm, minimum one minute. */
export function articleReadingMinutes(article: HelpArticle): number {
  const words = article.sections
    .flatMap((section) => [
      section.heading,
      ...section.blocks.flatMap((block) => {
        switch (block.kind) {
          case 'paragraph':
          case 'note':
          case 'warning':
            return [block.text]
          case 'steps':
            return block.items
          case 'code':
            return [block.code]
        }
      }),
    ])
    .join(' ')
    .split(/\s+/)
    .filter(Boolean).length
  return Math.max(1, Math.ceil(words / 180))
}

/**
 * Content integrity: unique ids/slugs, valid categories, resolvable
 * `relatedSlugs` and `articleSlug`, non-empty sections. The test suite
 * runs this over both locales; adding content cannot break links silently.
 */
export function checkHelpContent(corpus: HelpCorpus): string[] {
  const errors: string[] = []
  const slugs = new Set<string>()
  for (const article of corpus.articles) {
    if (slugs.has(article.slug)) errors.push(`duplicate article slug: ${article.slug}`)
    slugs.add(article.slug)
    if (!HELP_CATEGORIES.includes(article.category)) {
      errors.push(`article ${article.slug} has an unknown category: ${article.category}`)
    }
    if (article.sections.length === 0) errors.push(`article ${article.slug} has no sections`)
    for (const section of article.sections) {
      if (section.blocks.length === 0) {
        errors.push(`article ${article.slug} section ${section.id} has no blocks`)
      }
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(article.reviewedAt)) {
      errors.push(`article ${article.slug} has no real review date`)
    }
  }
  const ids = new Set<string>()
  for (const faq of corpus.faqs) {
    if (ids.has(faq.id)) errors.push(`duplicate FAQ id: ${faq.id}`)
    ids.add(faq.id)
    if (!HELP_CATEGORIES.includes(faq.category)) {
      errors.push(`FAQ ${faq.id} has an unknown category: ${faq.category}`)
    }
    if (faq.articleSlug && !slugs.has(faq.articleSlug)) {
      errors.push(`FAQ ${faq.id} links a missing article: ${faq.articleSlug}`)
    }
  }
  for (const article of corpus.articles) {
    for (const related of article.relatedSlugs) {
      if (!slugs.has(related)) errors.push(`article ${article.slug} links a missing article: ${related}`)
      if (related === article.slug) errors.push(`article ${article.slug} links itself`)
    }
  }
  const videoIds = new Set<string>()
  for (const video of corpus.videos) {
    if (videoIds.has(video.id)) errors.push(`duplicate video id: ${video.id}`)
    videoIds.add(video.id)
    if (!/^https:\/\//.test(video.url)) errors.push(`video ${video.id} has no https URL`)
  }
  return errors
}
