/**
 * The help center hub: `/help`.
 *
 * One search-first page, not a documentation tree: a hero search, four
 * quick-start actions into real routes, wrapping category pills, the
 * suggested guides, troubleshooting, an FAQ accordion and the (honestly
 * empty) video shelf. Search text and the chosen category live in the
 * query string (`?q=&cat=&faq=`), so a result is shareable and Back
 * restores the state.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { HELP_CATEGORIES, searchHelp } from '@/lib/help.ts'
import type { HelpArticle, HelpCategory, HelpFaq, HelpSearchResult } from '@/lib/help.ts'
import { HELP_SUGGESTED_SLUGS, useHelpCorpus, categoryLabel } from '@/help/corpus'
import { Highlight } from '@/components/help/helpUi'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { StringKey } from '@/i18n/fa.ts'
import { fa } from '@/lib/format'
import { articleReadingMinutes } from '@/lib/help.ts'
import './help.css'

type CategoryFilter = HelpCategory | 'all'

function validCategory(value: string | null): CategoryFilter {
  return value !== null && (HELP_CATEGORIES as readonly string[]).includes(value)
    ? (value as HelpCategory)
    : 'all'
}

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /mac/i.test(navigator.platform ?? '') || /mac/i.test(navigator.userAgent ?? '')
}

const QUICK: ReadonlyArray<{ to: string; titleKey: StringKey; hintKey: StringKey }> = [
  { to: '/workspace', titleKey: 'help.q1t', hintKey: 'help.q1h' },
  { to: '/jobs', titleKey: 'help.q2t', hintKey: 'help.q2h' },
  { to: '/convert', titleKey: 'help.q3t', hintKey: 'help.q3h' },
  { to: '/library', titleKey: 'help.q4t', hintKey: 'help.q4h' },
]

const USEFUL: ReadonlyArray<{ to: string; labelKey: 'nav.workspace' | 'nav.jobs' | 'nav.library' }> = [
  { to: '/workspace', labelKey: 'nav.workspace' },
  { to: '/jobs', labelKey: 'nav.jobs' },
  { to: '/library', labelKey: 'nav.library' },
]

function ArticleCard({ article, query }: { article: HelpArticle; query: string }) {
  const { t } = useLanguage()
  const from = query ? `/help?q=${encodeURIComponent(query)}` : '/help'
  return (
    <li>
      <Link
        to={`/help/articles/${article.slug}`}
        state={{ from }}
        className="surface-card card-link help-card"
      >
        <h3 className="help-card-title">
          <Highlight text={article.title} query={query} />
        </h3>
        <p className="help-card-summary">
          <Highlight text={article.summary} query={query} />
        </p>
        <span className="help-card-meta">
          <span className="badge">{categoryLabel(t, article.category)}</span>
          <span>{t('help.readingMinutes', { n: fa(articleReadingMinutes(article)) })}</span>
        </span>
      </Link>
    </li>
  )
}

function FaqItem({
  faq,
  open,
  onToggle,
  query,
}: {
  faq: HelpFaq
  open: boolean
  onToggle: () => void
  query: string
}) {
  const { t } = useLanguage()
  const answerId = `faq-a-${faq.id}`
  return (
    <li id={`faq-${faq.id}`} className="help-faq-item" data-open={open}>
      <button
        type="button"
        className="help-faq-q"
        aria-expanded={open}
        aria-controls={answerId}
        onClick={onToggle}
      >
        <span>
          <Highlight text={faq.question} query={query} />
        </span>
        <svg className="help-faq-chev" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div className="collapsible" data-open={open}>
        <div>
          <div id={answerId} className="help-faq-a">
            <p>
              <Highlight text={faq.answer} query={query} />
            </p>
            {faq.articleSlug ? (
              <p>
                <Link to={`/help/articles/${faq.articleSlug}`}>{t('help.faqArticleLink')}</Link>
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  )
}

function ResultRow({ result, query }: { result: HelpSearchResult; query: string }) {
  const { t } = useLanguage()
  const badge =
    result.kind === 'article' ? t('help.typeArticle') : result.kind === 'faq' ? t('help.typeFaq') : t('help.typeVideo')
  const to =
    result.kind === 'article'
      ? `/help/articles/${result.ref}`
      : `/help?faq=${encodeURIComponent(result.ref)}&cat=${result.category}`
  const state = result.kind === 'article' ? { from: `/help?q=${encodeURIComponent(query)}` } : undefined
  return (
    <li>
      <Link to={to} state={state} className="surface-card card-link help-card">
        <span className="help-card-meta" style={{ marginTop: 0, paddingTop: 0 }}>
          <span className="badge badge-accent">{badge}</span>
        </span>
        <span className="help-card-title">
          <Highlight text={result.title} query={query} />
        </span>
        <span className="help-card-summary">{result.summary.slice(0, 160)}</span>
      </Link>
    </li>
  )
}

export function HelpPage() {
  const { t, dir } = useLanguage()
  const { corpus } = useHelpCorpus()
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const category = validCategory(params.get('cat'))
  const openFaq = params.get('faq')

  const [raw, setRaw] = useState(query)
  const timer = useRef(0)

  // Back/Forward restores the URL; the field follows it.
  useEffect(() => {
    setRaw(query)
  }, [query])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const patchParams = (patch: { q?: string; cat?: CategoryFilter; faq?: string | null }) => {
    const next = new URLSearchParams(params)
    if (patch.q !== undefined) {
      if (patch.q) next.set('q', patch.q)
      else next.delete('q')
    }
    if (patch.cat !== undefined) {
      if (patch.cat === 'all') next.delete('cat')
      else next.set('cat', patch.cat)
    }
    if (patch.faq !== undefined) {
      if (patch.faq) next.set('faq', patch.faq)
      else next.delete('faq')
    }
    setParams(next, { replace: true })
  }

  const onQuery = (value: string) => {
    setRaw(value)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => patchParams({ q: value.trim() }), 250)
  }

  const results = useMemo(
    () => (query.trim() ? searchHelp(query, corpus, { category, limit: 20 }) : []),
    [query, corpus, category],
  )

  const articles = useMemo(
    () => corpus.articles.filter((a) => category === 'all' || a.category === category),
    [corpus, category],
  )
  const faqs = useMemo(
    () => corpus.faqs.filter((f) => category === 'all' || f.category === category),
    [corpus, category],
  )
  const suggested = useMemo(
    () => HELP_SUGGESTED_SLUGS.flatMap((slug) => corpus.articles.filter((a) => a.slug === slug)),
    [corpus],
  )
  const troubleshooting = useMemo(
    () => corpus.articles.filter((a) => a.category === 'troubleshooting'),
    [corpus],
  )

  // A linked FAQ (`?faq=`) opens and scrolls into view.
  useEffect(() => {
    if (!openFaq) return
    const node = document.getElementById(`faq-${openFaq}`)
    node?.scrollIntoView({ block: 'nearest' })
  }, [openFaq])

  const searching = query.trim().length > 0
  const showBrowse = !searching && category === 'all'

  return (
    <main className="page" dir={dir}>
      <header className="help-hero mb-[var(--spacing-6)]">
        <h1 className="help-hero-title">{t('help.title')}</h1>
        <p className="help-hero-sub">{t('help.lead')}</p>
        <div className="help-search-row">
          <input
            type="search"
            className="field"
            value={raw}
            onChange={(event) => onQuery(event.target.value)}
            placeholder={t('help.searchPh')}
            aria-label={t('help.searchLabel')}
          />
          <span className="help-kbd" aria-hidden="true">
            {isMac() ? '⌘K' : 'Ctrl+K'}
          </span>
        </div>
      </header>

      <section aria-label={t('help.quickStart')} className="mb-[var(--spacing-6)]">
        <h2 className="help-section-title">{t('help.quickStart')}</h2>
        <ul className="help-quick">
          {QUICK.map((item) => (
            <li key={item.to}>
              <Link to={item.to} className="help-quick-card">
                <span className="min-w-0">
                  <strong className="help-quick-title">{t(item.titleKey)}</strong>
                  <small className="help-quick-sub">{t(item.hintKey)}</small>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div className="help-tabs" role="group" aria-label={t('help.categoryLabel')}>
        {(['all', ...HELP_CATEGORIES] as const).map((key) => (
          <button
            key={key}
            type="button"
            className="help-tab"
            aria-pressed={category === key}
            onClick={() => patchParams({ cat: key })}
          >
            {key === 'all' ? t('help.allCats') : categoryLabel(t, key)}
          </button>
        ))}
      </div>

      {searching ? (
        <section aria-label={t('help.searchLabel')} aria-live="polite">
          {results.length > 0 ? (
            <>
              <p className="mb-[var(--spacing-3)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                {t('help.resultsFor', { n: fa(results.length), q: query.trim() })}
              </p>
              <ul className="help-grid">
                {results.map((result) => (
                  <ResultRow key={`${result.kind}:${result.ref}`} result={result} query={query} />
                ))}
              </ul>
            </>
          ) : (
            <div className="surface-card p-[var(--spacing-5)]">
              <h2 className="text-[length:var(--text-h3)] font-extrabold">
                {t('help.noResults', { q: query.trim() })}
              </h2>
              <div className="control-row mt-[var(--spacing-4)]">
                <button type="button" className="btn btn-secondary" onClick={() => patchParams({ q: '', cat: 'all' })}>
                  {t('help.clearFilters')}
                </button>
              </div>
              <p className="mt-[var(--spacing-4)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                {t('help.usefulLinks')}:
              </p>
              <div className="control-row mt-[var(--spacing-2)]">
                {USEFUL.map((item) => (
                  <Link key={item.to} to={item.to} className="btn btn-ghost">
                    {t(item.labelKey)}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </section>
      ) : (
        <>
          {showBrowse ? (
            <section aria-label={t('help.suggested')} className="mb-[var(--spacing-6)]">
              <h2 className="help-section-title">{t('help.suggested')}</h2>
              <ul className="help-grid">
                {suggested.map((article) => (
                  <ArticleCard key={article.slug} article={article} query="" />
                ))}
              </ul>
            </section>
          ) : (
            <section aria-label={t('help.categoryLabel')} className="mb-[var(--spacing-6)]">
              <ul className="help-grid">
                {articles.map((article) => (
                  <ArticleCard key={article.slug} article={article} query="" />
                ))}
              </ul>
            </section>
          )}

          {showBrowse ? (
            <section aria-label={t('help.troubleshooting')} className="mb-[var(--spacing-6)]">
              <h2 className="help-section-title">{t('help.troubleshooting')}</h2>
              <ul className="help-grid">
                {troubleshooting.map((article) => (
                  <ArticleCard key={article.slug} article={article} query="" />
                ))}
              </ul>
            </section>
          ) : null}

          <section aria-label={t('help.faq')} className="mb-[var(--spacing-6)]">
            <h2 className="help-section-title">{t('help.faq')}</h2>
            {faqs.length > 0 ? (
              <ul className="help-faq-list">
                {faqs.map((faq) => (
                  <FaqItem
                    key={faq.id}
                    faq={faq}
                    query=""
                    open={openFaq === faq.id}
                    onToggle={() => patchParams({ faq: openFaq === faq.id ? null : faq.id })}
                  />
                ))}
              </ul>
            ) : (
              <p className="empty">{t('help.dialogNone')}</p>
            )}
          </section>

          <section aria-label={t('help.videos')} className="mb-[var(--spacing-6)]">
            <h2 className="help-section-title">{t('help.videos')}</h2>
            {corpus.videos.length > 0 ? (
              <ul className="help-grid">
                {corpus.videos.map((video) => (
                  <li key={video.id} className="surface-card help-card">
                    <h3 className="help-card-title">{video.title}</h3>
                    <p className="help-card-summary">{video.description}</p>
                    <span className="help-card-meta">
                      <a href={video.url} target="_blank" rel="noreferrer">
                        {video.url}
                      </a>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="surface-card help-video-empty">
                <p className="m-0 text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                  {t('help.videosEmpty')} {t('help.videosEmptyHint')}
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
