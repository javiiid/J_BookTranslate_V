/**
 * One help article: `/help/articles/:slug`.
 *
 * Deep-linkable, refresh-safe and history-friendly: the slug resolves
 * from the URL alone, so Back/Forward and a pasted link all land here.
 * An unknown slug renders an explicit "not found" with a way back,
 * never a blank page. The "back" link returns to the exact search the
 * reader came from (kept in location state, not in the URL, so copied
 * links stay clean).
 */
import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { articleReadingMinutes } from '@/lib/help.ts'
import type { HelpBlock } from '@/lib/help.ts'
import { useHelpCorpus, categoryLabel } from '@/help/corpus'
import { useLanguage } from '@/i18n/useLanguage.ts'
import { fa, faDate } from '@/lib/format'
import './help.css'

function Block({ block }: { block: HelpBlock }) {
  switch (block.kind) {
    case 'paragraph':
      return <p>{block.text}</p>
    case 'steps':
      return (
        <ol className="help-steps">
          {block.items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ol>
      )
    case 'note':
      return <p className="alert alert-info">{block.text}</p>
    case 'warning':
      return <p className="alert alert-warning" role="alert">{block.text}</p>
    case 'code':
      return (
        <pre className="help-code" dir="ltr">
          {block.label ? <span className="help-code-label">{block.label}</span> : null}
          {block.code}
        </pre>
      )
  }
}

export function HelpArticlePage() {
  const { t, dir } = useLanguage()
  const { corpus } = useHelpCorpus()
  const { slug } = useParams()
  const location = useLocation()
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')

  const article = corpus.articles.find((a) => a.slug === slug)
  const from = (location.state as { from?: unknown } | null)?.from
  const backTo = typeof from === 'string' && from.startsWith('/help') ? from : '/help'

  if (!article) {
    return (
      <main className="page" dir={dir}>
        <div className="surface-card p-[var(--spacing-5)]">
          <h1 className="text-[length:var(--text-h1)] font-extrabold">{t('help.notFound')}</h1>
          <p className="mt-[var(--spacing-2)] text-[length:var(--text-body)]" style={{ color: 'var(--color-text-secondary)' }}>
            {t('help.notFoundBody')}
          </p>
          <Link to="/help" className="btn btn-primary mt-[var(--spacing-4)]">
            {t('help.backToHelp')}
          </Link>
        </div>
      </main>
    )
  }

  const related = article.relatedSlugs.flatMap((relatedSlug) =>
    corpus.articles.filter((a) => a.slug === relatedSlug),
  )

  const copyLink = async () => {
    try {
      if (!navigator.clipboard) throw new Error('no clipboard')
      await navigator.clipboard.writeText(window.location.href)
      setCopied('ok')
    } catch {
      setCopied('fail')
    }
  }

  return (
    <main className="page" dir={dir}>
      <nav className="help-crumb" aria-label={t('help.breadcrumb')}>
        <Link to="/help">{t('help.breadcrumb')}</Link>
        <span aria-hidden="true">/</span>
        <span>{categoryLabel(t, article.category)}</span>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{article.title}</span>
      </nav>

      <h1 className="text-[length:var(--text-h1)] font-extrabold">{article.title}</h1>
      <p className="mt-[var(--spacing-2)] max-w-[44rem] text-[length:var(--text-body)]" style={{ color: 'var(--color-text-secondary)' }}>
        {article.summary}
      </p>
      <div className="help-article-meta">
        <span className="badge">{categoryLabel(t, article.category)}</span>
        <span>{t('help.readingMinutes', { n: fa(articleReadingMinutes(article)) })}</span>
        <span>{t('help.reviewedAt', { date: faDate(article.reviewedAt) })}</span>
        <button type="button" className="btn btn-ghost" onClick={() => void copyLink()}>
          {t('help.copyLink')}
        </button>
      </div>
      <div aria-live="polite" className="mt-[var(--spacing-1)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
        {copied === 'ok' ? t('help.copied') : copied === 'fail' ? t('help.copyFailed') : ''}
      </div>

      {article.sections.length > 1 ? (
        <nav className="surface-card help-toc mt-[var(--spacing-5)]" aria-label={t('help.toc')}>
          <h2 className="help-toc-title">{t('help.toc')}</h2>
          <ul>
            {article.sections.map((section) => (
              <li key={section.id}>
                <a href={`#sec-${section.id}`}>{section.heading}</a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      <div className="mt-[var(--spacing-5)]">
        {article.sections.map((section) => (
          <section key={section.id} id={`sec-${section.id}`} className="help-section" aria-labelledby={`sec-h-${section.id}`}>
            <h2 id={`sec-h-${section.id}`}>{section.heading}</h2>
            <div className="help-prose">
              {section.blocks.map((block, index) => (
                <Block key={index} block={block} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {related.length > 0 ? (
        <section aria-label={t('help.related')} className="mt-[var(--spacing-6)]">
          <h2 className="help-section-title">{t('help.related')}</h2>
          <ul className="help-grid">
            {related.map((item) => (
              <li key={item.slug}>
                <Link to={`/help/articles/${item.slug}`} className="surface-card card-link help-card">
                  <h3 className="help-card-title">{item.title}</h3>
                  <p className="help-card-summary">{item.summary}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="control-row mt-[var(--spacing-6)]">
        <Link to={backTo} className="btn btn-secondary">
          {backTo === '/help' ? t('help.backToHelp') : t('help.backToResults')}
        </Link>
      </div>
    </main>
  )
}
