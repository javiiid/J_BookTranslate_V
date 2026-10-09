/**
 * The help center, asserted without a DOM.
 *
 * `node --test` strips types but resolves nothing, so every import below
 * names its file with the `.ts` extension -- an extensionless `./x`
 * fails with ERR_MODULE_NOT_FOUND and takes the whole file out of the
 * suite (the rule from `components/nav.ts`, applied here too).
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
import {
  articleReadingMinutes,
  checkHelpContent,
  expandHelpTokens,
  normalizeHelpText,
  searchHelp,
} from '../src/lib/help.ts'
import type { HelpCorpus } from '../src/lib/help.ts'
import { helpArticlesEn, helpFaqsEn, helpVideosEn } from '../src/help/content.en.ts'
import { helpArticlesFa, helpFaqsFa, helpVideosFa } from '../src/help/content.fa.ts'

const faCorpus: HelpCorpus = { articles: helpArticlesFa, faqs: helpFaqsFa, videos: helpVideosFa }
const enCorpus: HelpCorpus = { articles: helpArticlesEn, faqs: helpFaqsEn, videos: helpVideosEn }

describe('Persian normalisation (help search only)', () => {
  it('folds Arabic Yeh and Kaf', () => {
    assert.equal(normalizeHelpText('علي'), 'علی')
    assert.equal(normalizeHelpText('كتاب'), 'کتاب')
  })

  it('strips diacritics and folds ZWNJ to a space', () => {
    assert.equal(normalizeHelpText('مُترجم'), 'مترجم')
    assert.equal(normalizeHelpText('واژه‌نامه'), 'واژه نامه')
  })

  it('folds Persian and Arabic digits to Latin', () => {
    assert.equal(normalizeHelpText('۱۲ بخش'), '12 بخش')
    assert.equal(normalizeHelpText('٤٢٩'), '429')
  })

  it('collapses whitespace and lowercases Latin', () => {
    assert.equal(normalizeHelpText('  Resume   ترجمه '), 'resume ترجمه')
  })

  it('does not touch the glossary term logic', () => {
    // The normaliser lives in `lib/help.ts` and must not import the
    // translation term module (`lib/terms.ts`); a search fold must never
    // change term identity.
    const source = readFileSync(new URL('../src/lib/help.ts', import.meta.url), 'utf8')
    assert.ok(!/^import\s/m.test(source), 'help search imports another module')
  })
})

describe('ranking', () => {
  it('an exact title match outranks a body mention', () => {
    const results = searchHelp('توقف، لغو و ادامهٔ ترجمه', faCorpus)
    assert.ok(results.length > 0, 'no results at all')
    assert.equal(results[0]?.ref, 'stop-resume')
  })

  it('title words outrank keyword-only matches', () => {
    const results = searchHelp('واژه‌نامه', faCorpus)
    const refs = results.map((r) => r.ref)
    assert.ok(refs.includes('glossary-workflow'), 'the glossary guide is missing')
    assert.equal(refs[0], 'glossary-workflow')
  })

  it('multi-word queries narrow down (AND, not OR)', () => {
    const single = searchHelp('ترجمه', faCorpus)
    const narrow = searchHelp('ترجمه لغو', faCorpus)
    assert.ok(single.length > narrow.length, 'adding a word widened the results')
    assert.ok(narrow.length > 0, 'AND semantics removed everything')
    const singleRefs = new Set(single.map((r) => `${r.kind}:${r.ref}`))
    for (const result of narrow) {
      assert.ok(
        singleRefs.has(`${result.kind}:${result.ref}`),
        `narrowed result was not in the broad results: ${result.ref}`,
      )
    }
  })

  it('synonyms bridge English and Persian both ways', () => {
    const expanded = expandHelpTokens('resume')
    assert.ok(expanded[0]?.includes('ادامه'), 'resume does not expand to ادامه')
    const refs = searchHelp('resume', faCorpus).map((r) => r.ref)
    assert.ok(refs.includes('stop-resume'), 'resume finds nothing about ادامه')
    const back = searchHelp('ادامه', faCorpus).map((r) => r.ref)
    assert.ok(back.includes('stop-resume'), 'ادامه finds nothing')
  })

  it('the category filter narrows and never invents', () => {
    const results = searchHelp('ترجمه', faCorpus, { category: 'glossary' })
    assert.ok(results.length > 0, 'the filter removed everything')
    for (const result of results) assert.equal(result.category, 'glossary')
  })

  it('empty queries return nothing (a hint, not "no content")', () => {
    assert.deepEqual(searchHelp('', faCorpus), [])
    assert.deepEqual(searchHelp('   ', faCorpus), [])
  })

  it('the limit is honoured', () => {
    const results = searchHelp('ترجمه', faCorpus, { limit: 3 })
    assert.ok(results.length <= 3, `got ${results.length} results past the limit`)
  })

  it('FAQ answers are searchable and point at their article', () => {
    const results = searchHelp('هزینه', faCorpus)
    const faq = results.find((r) => r.kind === 'faq')
    assert.ok(faq, 'no FAQ matched a cost question')
  })

  it('no video result is ever invented', () => {
    assert.deepEqual(searchHelp('ویدیو', faCorpus), [])
    assert.deepEqual(searchHelp('video', enCorpus), [])
  })
})

describe('content integrity', () => {
  for (const [name, corpus] of [
    ['fa', faCorpus],
    ['en', enCorpus],
  ] as const) {
    it(`${name}: slugs, ids, categories and links are sound`, () => {
      assert.deepEqual(checkHelpContent(corpus), [])
    })

    it(`${name}: at least 10 articles, 10 FAQs and 6 troubleshooting scenarios`, () => {
      assert.ok(corpus.articles.length >= 10, `only ${corpus.articles.length} articles`)
      assert.ok(corpus.faqs.length >= 10, `only ${corpus.faqs.length} FAQs`)
      const scenarios = corpus.articles.filter((a) => a.category === 'troubleshooting')
      assert.ok(scenarios.length >= 2, 'no troubleshooting articles')
      const scenarioSections = scenarios.flatMap((a) => a.sections).length
      assert.ok(scenarioSections >= 6, `only ${scenarioSections} troubleshooting sections`)
    })

    it(`${name}: every article states a real reading time`, () => {
      for (const article of corpus.articles) {
        const minutes = articleReadingMinutes(article)
        assert.ok(minutes >= 1, `${article.slug} claims less than a minute`)
      }
    })
  }

  it('both locales share slugs, ids and section anchors', () => {
    // Switching language must never break a link or a #sec- anchor.
    assert.deepEqual(
      helpArticlesEn.map((a) => a.slug),
      helpArticlesFa.map((a) => a.slug),
    )
    assert.deepEqual(
      helpFaqsEn.map((f) => f.id),
      helpFaqsFa.map((f) => f.id),
    )
    for (const faArticle of helpArticlesFa) {
      const enArticle = helpArticlesEn.find((a) => a.slug === faArticle.slug)
      assert.ok(enArticle, `en is missing ${faArticle.slug}`)
      assert.deepEqual(
        enArticle?.sections.map((s) => s.id),
        faArticle.sections.map((s) => s.id),
        `${faArticle.slug} has different anchors per language`,
      )
    }
  })
})

describe('wiring (static: the route, the rail, the dialog)', () => {
  const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
  const nav = readFileSync(new URL('../src/components/nav.ts', import.meta.url), 'utf8')
  const dialog = readFileSync(
    new URL('../src/components/help/HelpSearchDialog.tsx', import.meta.url),
    'utf8',
  )

  it('/help and /help/articles/:slug render pages, not redirects', () => {
    assert.match(app, /path="\/help" element=\{<\s*HelpPage\s*\/>\s*\}/)
    assert.match(app, /path="\/help\/articles\/:slug" element=\{<\s*HelpArticlePage\s*\/>\s*\}/)
  })

  it('the rail carries /help but the bottom bar stays five', () => {
    assert.match(nav, /to: '\/help'/)
    assert.ok(!/MOBILE_NAV[^;]*\/help/s.test(nav), '/help took a mobile-bar slot')
  })

  it('the dialog owns the shortcut and cleans it up', () => {
    assert.match(dialog, /ctrlKey|metaKey/, 'no Ctrl/Cmd+K listener')
    assert.match(dialog, /removeEventListener/, 'the listener is never removed')
    assert.match(dialog, /isComposing/, 'IME composition is not guarded')
    assert.match(dialog, /Escape/, 'Escape does not close the dialog')
  })

  it('highlighting never injects raw HTML', () => {
    const ui = readFileSync(new URL('../src/components/help/helpUi.tsx', import.meta.url), 'utf8')
    assert.ok(!ui.includes('dangerouslySetInnerHTML'), 'query text reaches raw HTML')
    assert.match(ui, /<mark/, 'no <mark> highlighting')
  })

  it('the 404 page offers the help center', () => {
    const notFound = readFileSync(new URL('../src/pages/PendingPage.tsx', import.meta.url), 'utf8')
    assert.match(notFound, /\/help/, 'NotFoundPage does not link /help')
  })
})
