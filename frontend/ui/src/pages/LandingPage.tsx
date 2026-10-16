/**
 * The landing page, in React. Bilingual (Persian/English) through the shared
 * `landing.*` dictionary namespace -- the same contract every converted page
 * follows (`tests/i18n.test.ts` holds fa/en parity).
 *
 * Marketing surface for KALIMA (کالیما), built only on the project's own
 * tokens (`src/styles/tokens.css`) plus the page-owned `landing.css` next to
 * this file -- the same split `library.css` and `conversion.css` use.
 *
 * Every number on this page is a verified fact from the Python project that
 * is the single source of truth:
 *   12 workers / 10.9x ............ readme.md benchmark table (72.2s -> 6.6s)
 *   12 samples -> 1 call ........... app/glossary/proposal.py + readme.md
 *   5 monitor tabs .................. app/jobs/detail_page.py
 *   10 output formats ............... app/output/formats.py registry
 *   6 quality dimensions ............ app/pipeline/quality_scorer.py
 *   4 account plans ................. app/account/service.py PLANS
 *   11 languages .................... the language selects in app/web.py
 *
 * Rules honoured: semantic tokens only (no hex, no Tailwind colour classes),
 * shared chrome (KalimaMark, ThemeToggle, LanguageToggle), the `.page`
 * gutter, Lucide-stroke icons (no emoji), `dir` from the language provider,
 * visible focus from tokens.css, `prefers-reduced-motion` respected, zero
 * new dependencies.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { KalimaMark, LanguageToggle, ThemeToggle } from '@/components/AppShell'
import { NavIcon } from '@/components/NavIcon'
import type { NavIconName } from '@/components/nav'
import { api } from '@/lib/api.ts'
import { useLanguage } from '@/i18n/useLanguage.ts'
import type { Language } from '@/i18n/lang.ts'
import './landing.css'

/* ------------------------------------------------------------------ */
/* Page metadata, in the active language. The SPA serves one index.html */
/* for every route, so the landing sets its own title and description  */
/* on mount and refreshes them on a language toggle. No domain is      */
/* invented here: canonical/URL tags are left out on purpose.           */
/* ------------------------------------------------------------------ */
function useLandingSeo(lang: Language): void {
  useEffect(() => {
    const english = lang === 'en'
    document.title = english
      ? 'KALIMA | AI book translation that keeps the meaning'
      : 'کالیما | ترجمهٔ کتاب با هوش مصنوعی، بدون از دست رفتن معنا'
    const description = english
      ? 'KALIMA translates long EPUB and PDF books chunk by chunk: uniform project memory, a glossary you approve, safe stop and resume, and 10 output formats.'
      : 'کالیما کتاب‌های بلند EPUB و PDF را بخش‌به‌بخش ترجمه می‌کند: حافظهٔ یکدست پروژه، واژه‌نامه‌ای که خودتان تأیید می‌کنید، توقف و ادامهٔ امن، و ۱۰ قالب خروجی.'
    const setMeta = (selector: string, field: 'name' | 'property', name: string, content: string): void => {
      let tag = document.head.querySelector(selector)
      if (tag === null) {
        const created = document.createElement('meta')
        created.setAttribute(field, name)
        document.head.appendChild(created)
        tag = created
      }
      tag.setAttribute('content', content)
    }
    setMeta('meta[name="description"]', 'name', 'description', description)
    setMeta(
      'meta[property="og:title"]',
      'property',
      'og:title',
      english ? 'KALIMA | AI book translation' : 'کالیما | ترجمهٔ کتاب با هوش مصنوعی',
    )
    setMeta('meta[property="og:description"]', 'property', 'og:description', description)
    setMeta('meta[property="og:type"]', 'property', 'og:type', 'website')
    setMeta('meta[name="twitter:card"]', 'name', 'twitter:card', 'summary')
  }, [lang])
}

/* ------------------------------------------------------------------ */
/* Entrance motion without a library: the hook adds the class (so the   */
/* page stays fully visible with no JS) and an IntersectionObserver     */
/* reveals each section once. Reduced motion skips it entirely.          */
/* ------------------------------------------------------------------ */
function useReveal(): void {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll('[data-reveal]'))
    if (els.length === 0) return
    const show = (el: Element): void => {
      el.classList.add('landing-reveal', 'is-visible')
    }
    if (
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      !('IntersectionObserver' in window)
    ) {
      els.forEach(show)
      return
    }
    const pending = new Set<Element>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            io.unobserve(entry.target)
            pending.delete(entry.target)
          }
        }
      },
      { threshold: 0.08 },
    )
    for (const el of els) {
      el.classList.add('landing-reveal')
      pending.add(el)
      io.observe(el)
    }
    return () => io.disconnect()
  }, [])
}

interface Anchor {
  href: string
  label: string
}

interface Feature {
  icon: NavIconName
  to: string
  cta: string
  title: string
  what: string
  why: string
  mini: 'parallel' | 'glossary' | 'snapshot' | 'resume' | 'monitor' | 'calibration'
}

interface BenchRow {
  label: string
  time: string
  speedup: string
  width: number
}

interface Step {
  index: string
  title: string
  body: string
}

interface UseCase {
  title: string
  body: string
}

interface CompareRow {
  dim: string
  generic: string
  kalima: string
}

interface Plan {
  id: string
  to: string
  name: string
  blurb: string
  price: string
  per: string
  features: string[]
  cta: string
}

interface Faq {
  q: string
  a: string
}

function CheckIcon(): React.JSX.Element {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

function ArrowIcon(): React.JSX.Element {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  )
}

/* Decorative "translation flow": dots streaming from source to translation.
   Pure CSS (see landing.css), aria-hidden, frozen under reduced motion. */
function TranslationFlow(): React.JSX.Element {
  const { t } = useLanguage()
  return (
    <div className="landing-flow" aria-hidden="true">
      <span className="landing-flow-label">{t('landing.hero.flowFrom')}</span>
      <span className="landing-flow-track">
        <span className="landing-flow-dot" />
        <span className="landing-flow-dot" />
        <span className="landing-flow-dot" />
      </span>
      <span className="landing-flow-label">{t('landing.hero.flowTo')}</span>
    </div>
  )
}

function FeatureMini({ kind }: { kind: Feature['mini'] }): React.JSX.Element {
  const { t } = useLanguage()
  if (kind === 'glossary') {
    const terms = [
      t('landing.mini.term1'),
      t('landing.mini.term2'),
      t('landing.mini.term3'),
      t('landing.mini.term4'),
      t('landing.mini.term5'),
      t('landing.mini.term6'),
    ]
    return (
      <div className="landing-mini" aria-hidden="true">
        <div className="flex flex-wrap gap-[var(--spacing-1)]">
          {terms.map((term) => (
            <span key={term} className="badge">
              {term}
            </span>
          ))}
        </div>
      </div>
    )
  }
  if (kind === 'parallel') {
    const rows = [
      { label: t('landing.mini.chunk1'), width: 86 },
      { label: t('landing.mini.chunk2'), width: 63 },
      { label: t('landing.mini.chunk3'), width: 40 },
    ]
    return (
      <div className="landing-mini" aria-hidden="true">
        {rows.map((row) => (
          <div key={row.label} className="landing-mini-row">
            <span style={{ minWidth: '3.5rem' }}>{row.label}</span>
            <span className="progress-track" style={{ flex: 1 }}>
              <span className="progress-fill" style={{ width: `${row.width}%` }} />
            </span>
          </div>
        ))}
      </div>
    )
  }
  if (kind === 'snapshot') {
    return (
      <div className="landing-mini" aria-hidden="true">
        <div className="landing-mini-row">
          <span className="badge badge-info">{t('landing.mini.snap1')}</span>
          <span aria-hidden="true">←</span>
          <span className="badge badge-accent">{t('landing.mini.snap2')}</span>
          <span aria-hidden="true">←</span>
          <span className="badge">{t('landing.mini.snap3')}</span>
        </div>
      </div>
    )
  }
  if (kind === 'resume') {
    return (
      <div className="landing-mini" aria-hidden="true">
        <div className="landing-mini-row">
          <span className="badge badge-success">{t('landing.mini.resumeBadge')}</span>
        </div>
        <div className="landing-mini-row">
          <span>{t('landing.mini.resumeNote')}</span>
        </div>
      </div>
    )
  }
  if (kind === 'monitor') {
    const tabs = [
      t('landing.mini.tab1'),
      t('landing.mini.tab2'),
      t('landing.mini.tab3'),
      t('landing.mini.tab4'),
      t('landing.mini.tab5'),
    ]
    return (
      <div className="landing-mini" aria-hidden="true">
        <div className="flex flex-wrap gap-[var(--spacing-1)]">
          {tabs.map((tab) => (
            <span key={tab} className="badge badge-info">
              {tab}
            </span>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="landing-mini" aria-hidden="true">
      <div className="landing-mini-row">
        <span className="badge">{t('landing.mini.cal1')}</span>
        <span className="badge">{t('landing.mini.cal2')}</span>
        <span className="badge">{t('landing.mini.cal3')}</span>
        <span aria-hidden="true">←</span>
        <span className="badge badge-success">{t('landing.mini.calLocked')}</span>
      </div>
    </div>
  )
}

/* Verified benchmark (readme.md: 12 chunks, request count fixed at 24).
   Real figures, readable text -- not decoration, so not aria-hidden. */
function BenchmarkChart(): React.JSX.Element {
  const { t } = useLanguage()
  const rows: BenchRow[] = [
    { label: t('landing.bench.b1l'), time: t('landing.bench.b1t'), speedup: t('landing.bench.b1x'), width: 100 },
    { label: t('landing.bench.b2l'), time: t('landing.bench.b2t'), speedup: t('landing.bench.b2x'), width: 33.5 },
    { label: t('landing.bench.b3l'), time: t('landing.bench.b3t'), speedup: t('landing.bench.b3x'), width: 17 },
    { label: t('landing.bench.b4l'), time: t('landing.bench.b4t'), speedup: t('landing.bench.b4x'), width: 9.1 },
  ]
  return (
    <div>
      <div className="landing-bench">
        {rows.map((row) => (
          <div key={row.label} className="landing-bench-row">
            <span className="landing-bench-label">{row.label}</span>
            <span className="landing-bench-track" aria-hidden="true">
              <span className="landing-bench-fill" style={{ width: `${row.width}%` }} />
            </span>
            <span className="landing-bench-value">
              {row.time} · {row.speedup}
            </span>
          </div>
        ))}
      </div>
      <p className="landing-bench-note">{t('landing.bench.note')}</p>
    </div>
  )
}

/* Hand-drawn open book for the closing band. Token strokes only, aria-hidden,
   gently floating with the same motion system as the hero cards. */
function CtaBookArt(): React.JSX.Element {
  return (
    <svg
      width={180}
      height={128}
      viewBox="0 0 180 128"
      role="presentation"
      aria-hidden="true"
      focusable="false"
      className="landing-float mx-auto mb-[var(--spacing-4)]"
    >
      <path className="landing-art-line" d="M90 26 C 70 18, 44 18, 28 25 L28 96 C 44 89, 70 89, 90 97 Z" />
      <path className="landing-art-line" d="M90 26 C 110 18, 136 18, 152 25 L152 96 C 136 89, 110 89, 90 97 Z" />
      <path className="landing-art-line" d="M90 26 L90 97" />
      <rect className="landing-art-mid" x={40} y={44} width={36} height={5} rx={2.5} />
      <rect className="landing-art-mid" x={40} y={54} width={28} height={5} rx={2.5} />
      <rect className="landing-art-mid" x={40} y={64} width={32} height={5} rx={2.5} />
      <rect className="landing-art-mid" x={104} y={44} width={36} height={5} rx={2.5} />
      <rect className="landing-art-mid" x={112} y={54} width={28} height={5} rx={2.5} />
      <rect className="landing-art-mid" x={108} y={64} width={32} height={5} rx={2.5} />
      <path className="landing-art-soft" d="M132 30 L142 30 L137 52 Z" />
      <circle className="landing-art-mid" cx={34} cy={22} r={3} />
      <circle className="landing-art-mid" cx={150} cy={14} r={2.5} />
      <path className="landing-art-line landing-art-faint" d="M52 14 h8 M56 10 v8" />
      <path className="landing-art-line landing-art-faint" d="M122 108 h8 M126 104 v8" />
    </svg>
  )
}

export function LandingPage(): React.JSX.Element {
  const { t, dir, lang } = useLanguage()
  useLandingSeo(lang)
  useReveal()
  const [menuOpen, setMenuOpen] = useState<boolean>(false)
  /* null = still checking; a name = signed in; '' = signed out. The navbar
     login action becomes the account action for a signed-in visitor. */
  const [accountName, setAccountName] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    void api
      .authMe()
      .then((me) => {
        if (!cancelled) setAccountName(me.user.display_name || me.user.email)
      })
      .catch(() => {
        if (!cancelled) setAccountName('')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const anchors: Anchor[] = [
    { href: '#product', label: t('landing.nav.product') },
    { href: '#features', label: t('landing.nav.features') },
    { href: '#how', label: t('landing.nav.how') },
    { href: '#pricing', label: t('landing.nav.pricing') },
    { href: '#faq', label: t('landing.nav.faq') },
  ]

  const proofs = [
    { value: t('landing.proof.v1'), label: t('landing.proof.l1'), hint: t('landing.proof.h1') },
    { value: t('landing.proof.v2'), label: t('landing.proof.l2'), hint: t('landing.proof.h2') },
    { value: t('landing.proof.v3'), label: t('landing.proof.l3'), hint: t('landing.proof.h3') },
    { value: t('landing.proof.v4'), label: t('landing.proof.l4'), hint: t('landing.proof.h4') },
  ]

  const problems = [
    t('landing.problem.p1'),
    t('landing.problem.p2'),
    t('landing.problem.p3'),
    t('landing.problem.p4'),
    t('landing.problem.p5'),
  ]

  const solutions = [
    t('landing.problem.s1'),
    t('landing.problem.s2'),
    t('landing.problem.s3'),
    t('landing.problem.s4'),
  ]

  const features: Feature[] = [
    {
      icon: 'monitor',
      to: '/jobs',
      cta: t('landing.features.ctaMonitor'),
      title: t('landing.features.f1t'),
      what: t('landing.features.f1w'),
      why: t('landing.features.f1y'),
      mini: 'parallel',
    },
    {
      icon: 'library',
      to: '/library',
      cta: t('landing.features.ctaLibrary'),
      title: t('landing.features.f2t'),
      what: t('landing.features.f2w'),
      why: t('landing.features.f2y'),
      mini: 'glossary',
    },
    {
      icon: 'dashboard',
      to: '/jobs',
      cta: t('landing.features.ctaMonitor'),
      title: t('landing.features.f3t'),
      what: t('landing.features.f3w'),
      why: t('landing.features.f3y'),
      mini: 'snapshot',
    },
    {
      icon: 'convert',
      to: '/jobs',
      cta: t('landing.features.ctaMonitor'),
      title: t('landing.features.f4t'),
      what: t('landing.features.f4w'),
      why: t('landing.features.f4y'),
      mini: 'resume',
    },
    {
      icon: 'reader',
      to: '/jobs',
      cta: t('landing.features.ctaMonitor'),
      title: t('landing.features.f5t'),
      what: t('landing.features.f5w'),
      why: t('landing.features.f5y'),
      mini: 'monitor',
    },
    {
      icon: 'add',
      to: '/workspace',
      cta: t('landing.features.ctaWorkspace'),
      title: t('landing.features.f6t'),
      what: t('landing.features.f6w'),
      why: t('landing.features.f6y'),
      mini: 'calibration',
    },
  ]

  const annotations = [
    { key: t('landing.showcase.a1k'), body: t('landing.showcase.a1b') },
    { key: t('landing.showcase.a2k'), body: t('landing.showcase.a2b') },
    { key: t('landing.showcase.a3k'), body: t('landing.showcase.a3b') },
    { key: t('landing.showcase.a4k'), body: t('landing.showcase.a4b') },
    { key: t('landing.showcase.a5k'), body: t('landing.showcase.a5b') },
  ]

  const steps: Step[] = [
    { index: t('landing.steps.idx1'), title: t('landing.steps.s1t'), body: t('landing.steps.s1b') },
    { index: t('landing.steps.idx2'), title: t('landing.steps.s2t'), body: t('landing.steps.s2b') },
    { index: t('landing.steps.idx3'), title: t('landing.steps.s3t'), body: t('landing.steps.s3b') },
    { index: t('landing.steps.idx4'), title: t('landing.steps.s4t'), body: t('landing.steps.s4b') },
  ]

  const cases: UseCase[] = [
    { title: t('landing.cases.c1t'), body: t('landing.cases.c1b') },
    { title: t('landing.cases.c2t'), body: t('landing.cases.c2b') },
    { title: t('landing.cases.c3t'), body: t('landing.cases.c3b') },
    { title: t('landing.cases.c4t'), body: t('landing.cases.c4b') },
  ]

  const compare: CompareRow[] = [
    { dim: t('landing.why.w1d'), generic: t('landing.why.w1g'), kalima: t('landing.why.w1k') },
    { dim: t('landing.why.w2d'), generic: t('landing.why.w2g'), kalima: t('landing.why.w2k') },
    { dim: t('landing.why.w3d'), generic: t('landing.why.w3g'), kalima: t('landing.why.w3k') },
    { dim: t('landing.why.w4d'), generic: t('landing.why.w4g'), kalima: t('landing.why.w4k') },
    { dim: t('landing.why.w5d'), generic: t('landing.why.w5g'), kalima: t('landing.why.w5k') },
  ]

  const formats = [
    { name: t('landing.formats.m1n'), hint: t('landing.formats.m1h') },
    { name: t('landing.formats.m2n'), hint: t('landing.formats.m2h') },
    { name: t('landing.formats.m3n'), hint: t('landing.formats.m3h') },
    { name: t('landing.formats.m4n'), hint: t('landing.formats.m4h') },
    { name: t('landing.formats.m5n'), hint: t('landing.formats.m5h') },
    { name: t('landing.formats.m6n'), hint: t('landing.formats.m6h') },
    { name: t('landing.formats.m7n'), hint: t('landing.formats.m7h') },
    { name: t('landing.formats.m8n'), hint: t('landing.formats.m8h') },
    { name: t('landing.formats.m9n'), hint: t('landing.formats.m9h') },
    { name: t('landing.formats.m10n'), hint: t('landing.formats.m10h') },
  ]

  const security = [
    { title: t('landing.security.s1t'), body: t('landing.security.s1b') },
    { title: t('landing.security.s2t'), body: t('landing.security.s2b') },
    { title: t('landing.security.s3t'), body: t('landing.security.s3b') },
  ]

  /* Presented consistently with app/account/service.py PLANS -- same four
     plans, same prices, same feature keys translated. */
  const plans: Plan[] = [
    {
      id: 'free',
      to: '/workspace',
      name: t('landing.pricing.p1name'),
      blurb: t('landing.pricing.p1blurb'),
      price: t('landing.pricing.p1price'),
      per: t('landing.pricing.p1per'),
      features: [t('landing.pricing.p1f1'), t('landing.pricing.p1f2')],
      cta: t('landing.pricing.p1cta'),
    },
    {
      id: 'pro',
      to: '/account',
      name: t('landing.pricing.p2name'),
      blurb: t('landing.pricing.p2blurb'),
      price: t('landing.pricing.p2price'),
      per: t('landing.pricing.p2per'),
      features: [
        t('landing.pricing.p2f1'),
        t('landing.pricing.p2f2'),
        t('landing.pricing.p2f3'),
        t('landing.pricing.p2f4'),
      ],
      cta: t('landing.pricing.p2cta'),
    },
    {
      id: 'publisher',
      to: '/account',
      name: t('landing.pricing.p3name'),
      blurb: t('landing.pricing.p3blurb'),
      price: t('landing.pricing.p3price'),
      per: t('landing.pricing.p3per'),
      features: [
        t('landing.pricing.p3f1'),
        t('landing.pricing.p3f2'),
        t('landing.pricing.p3f3'),
        t('landing.pricing.p3f4'),
      ],
      cta: t('landing.pricing.p3cta'),
    },
    {
      id: 'enterprise',
      to: '/account',
      name: t('landing.pricing.p4name'),
      blurb: t('landing.pricing.p4blurb'),
      price: t('landing.pricing.p4price'),
      per: '',
      features: [
        t('landing.pricing.p4f1'),
        t('landing.pricing.p4f2'),
        t('landing.pricing.p4f3'),
        t('landing.pricing.p4f4'),
      ],
      cta: t('landing.pricing.p4cta'),
    },
  ]

  const faqs: Faq[] = [
    { q: t('landing.faq.q1'), a: t('landing.faq.a1') },
    { q: t('landing.faq.q2'), a: t('landing.faq.a2') },
    { q: t('landing.faq.q3'), a: t('landing.faq.a3') },
    { q: t('landing.faq.q4'), a: t('landing.faq.a4') },
    { q: t('landing.faq.q5'), a: t('landing.faq.a5') },
    { q: t('landing.faq.q6'), a: t('landing.faq.a6') },
    { q: t('landing.faq.q7'), a: t('landing.faq.a7') },
    { q: t('landing.faq.q8'), a: t('landing.faq.a8') },
  ]

  const footerAnchors: Anchor[] = [
    { href: '#features', label: t('landing.nav.features') },
    { href: '#product', label: t('landing.footer.productShow') },
    { href: '#how', label: t('landing.nav.how') },
    { href: '#pricing', label: t('landing.nav.pricing') },
    { href: '#faq', label: t('landing.nav.faq') },
  ]

  return (
    <main className="page" dir={dir} id="top">
      <div className="landing-shell">
        {/* ---- Navbar: anchors, login, primary CTA, mobile hamburger ---- */}
        <header className="landing-nav">
          <div className="landing-nav-inner">
            <a className="landing-brand" href="#top" aria-label={t('landing.brandAria')}>
              <KalimaMark size={32} />
              <span className="min-w-0">
                <strong className="block text-[length:var(--text-small)] tracking-wide">KALIMA</strong>
                <small
                  className="block text-[length:var(--text-caption)]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {t('landing.brandTag')}
                </small>
              </span>
            </a>
            <nav className="landing-links" aria-label={t('landing.mobileNavAria')}>
              {anchors.map((a) => (
                <a key={a.href} href={a.href}>
                  {a.label}
                </a>
              ))}
            </nav>
            <span className="landing-nav-actions">
              <span className="tool-cluster">
                <ThemeToggle />
                <span className="tool-divider landing-lang-narrow" aria-hidden="true" />
                <span className="landing-lang-narrow">
                  <LanguageToggle />
                </span>
              </span>
              <Link to={accountName ? '/account' : '/login'} className="btn btn-ghost landing-login">
                {accountName || t('landing.login')}
              </Link>
              <Link to="/workspace" className="btn btn-primary">
                {t('landing.cta')}
              </Link>
              <button
                type="button"
                className="btn-icon landing-menu-btn"
                aria-expanded={menuOpen}
                aria-controls="landing-menu"
                aria-label={menuOpen ? t('landing.menuClose') : t('landing.menuOpen')}
                onClick={() => setMenuOpen((open) => !open)}
              >
                <svg
                  width={20}
                  height={20}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  aria-hidden="true"
                  focusable="false"
                >
                  {menuOpen ? <path d="M18 6 6 18M6 6l12 12" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
                </svg>
              </button>
            </span>
          </div>
          {menuOpen ? (
            <nav className="landing-menu" id="landing-menu" aria-label={t('landing.mobileNavAria')}>
              {anchors.map((a) => (
                <a key={a.href} href={a.href} onClick={() => setMenuOpen(false)}>
                  {a.label}
                </a>
              ))}
              <Link to={accountName ? '/account' : '/login'} onClick={() => setMenuOpen(false)}>
                {accountName || t('landing.accountLink')}
              </Link>
              <div className="landing-menu-actions">
                <LanguageToggle />
                <span>{t('landing.switchLang')}</span>
              </div>
            </nav>
          ) : null}
        </header>

        {/* ---- Hero: promise, proof of work, dual CTA, real preview ---- */}
        <section aria-labelledby="landing-hero" className="landing-section landing-hero-glow mt-[var(--spacing-8)]">
          <div className="landing-hero">
            <div className="min-w-0">
              <p className="landing-eyebrow">
                <span dir="ltr" lang="en">
                  AI-POWERED BOOK TRANSLATION
                </span>
              </p>
              <h1 id="landing-hero" className="landing-hero-title">
                {t('landing.hero.title')}
              </h1>
              <p className="landing-lead mt-[var(--spacing-3)] max-w-[38rem]">{t('landing.hero.lead')}</p>
              <div className="control-row mt-[var(--spacing-5)]">
                <Link to="/workspace" className="btn btn-primary">
                  {t('landing.hero.cta1')}
                </Link>
                <a href="#how" className="btn btn-secondary">
                  {t('landing.hero.cta2')}
                </a>
              </div>
              <ul
                className="mt-[var(--spacing-4)] flex flex-wrap items-center gap-[var(--spacing-3)] text-[length:var(--text-caption)]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {[t('landing.hero.trust1'), t('landing.hero.trust2'), t('landing.hero.trust3')].map(
                  (item) => (
                    <li key={item} className="flex items-center gap-[var(--spacing-1)]">
                      <span style={{ color: 'var(--color-success)' }}>
                        <CheckIcon />
                      </span>
                      {item}
                    </li>
                  ),
                )}
              </ul>
            </div>
            <div className="landing-preview" role="img" aria-label={t('landing.hero.previewAria')}>
              <div className="landing-preview-card" aria-hidden="true">
                <p className="landing-preview-cap">{t('landing.hero.previewCap')}</p>
                <div className="mt-[var(--spacing-3)] grid gap-[var(--spacing-2)]">
                  <p dir="ltr" lang="en" className="landing-sample-src" style={{ textAlign: 'left' }}>
                    The narrator paused at the edge of the square, listening to the city wake up.
                  </p>
                  <TranslationFlow />
                  <p className="landing-sample-dst">راوی لب میدان ایستاد و به بیدار شدن شهر گوش سپرد.</p>
                </div>
                <div className="mt-[var(--spacing-3)]">
                  <div className="flex items-center justify-between text-[length:var(--text-caption)]">
                    <span style={{ color: 'var(--color-text-muted)' }}>{t('landing.hero.liveLabel')}</span>
                    <strong style={{ color: 'var(--color-text-primary)' }}>{t('landing.hero.liveValue')}</strong>
                  </div>
                  <div className="progress-track mt-[var(--spacing-2)]">
                    <div className="progress-fill" style={{ width: '64%' }} />
                  </div>
                </div>
              </div>
              <div className="mt-[var(--spacing-3)] grid gap-[var(--spacing-3)] sm:grid-cols-2">
                <div
                  className="landing-float rounded-[var(--radius-card)] border p-[var(--spacing-4)]"
                  style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                  aria-hidden="true"
                >
                  <p className="landing-preview-cap">{t('landing.hero.glossCap')}</p>
                  <p
                    className="mt-[var(--spacing-1)] text-[length:var(--text-h3)] font-extrabold"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {t('landing.hero.glossTitle')}
                  </p>
                  <p className="text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                    {t('landing.hero.glossBody')}
                  </p>
                </div>
                <div
                  className="landing-float landing-float-alt rounded-[var(--radius-card)] border p-[var(--spacing-4)]"
                  style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                  aria-hidden="true"
                >
                  <p className="landing-preview-cap">{t('landing.hero.concCap')}</p>
                  <p
                    className="mt-[var(--spacing-1)] text-[length:var(--text-h3)] font-extrabold"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {t('landing.hero.concTitle')}
                  </p>
                  <p className="text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                    {t('landing.hero.concBody')}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---- Proof: capability figures, never testimonials ---- */}
        <section aria-label={t('landing.proof.l1')} className="landing-section mt-[var(--spacing-8)]" data-reveal>
          <div className="landing-proof">
            {proofs.map((s) => (
              <div key={s.label} className="surface-card min-w-0 p-[var(--spacing-4)]">
                <strong className="landing-proof-value">{s.value}</strong>
                <span className="landing-proof-label">{s.label}</span>
                <span className="landing-proof-hint">{s.hint}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ---- Benchmark: measured speedup as a chart, not a claim ---- */}
        <section aria-labelledby="bench-title" className="landing-section mt-[var(--spacing-8)]" data-reveal>
          <div className="surface-card min-w-0 p-[var(--spacing-4)] sm:p-[var(--spacing-6)]">
            <h2 id="bench-title" className="text-[length:var(--text-h2)] font-extrabold">
              {t('landing.bench.title')}
            </h2>
            <p className="landing-section-sub">{t('landing.bench.body')}</p>
            <div className="mt-[var(--spacing-4)]">
              <BenchmarkChart />
            </div>
          </div>
        </section>

        {/* ---- Problem -> solution ---- */}
        <section aria-labelledby="problem-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="problem-title" className="landing-section-title">
              {t('landing.problem.title')}
            </h2>
          </div>
          <div className="landing-split mt-[var(--spacing-6)]">
            <div className="surface-card min-w-0 p-[var(--spacing-4)]">
              <h3 className="text-[length:var(--text-h3)] font-bold">{t('landing.problem.h')}</h3>
              <ul className="landing-problem-list">
                {problems.map((item) => (
                  <li key={item}>
                    <span className="landing-marker-bad" aria-hidden="true">
                      ✕
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="surface-card min-w-0 p-[var(--spacing-4)]">
              <h3 className="text-[length:var(--text-h3)] font-bold">{t('landing.problem.solutionH')}</h3>
              <ul className="landing-solution-list">
                {solutions.map((item) => (
                  <li key={item}>
                    <span className="landing-marker-good" aria-hidden="true">
                      <CheckIcon />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---- Core features: what it does + why it matters ---- */}
        <section id="features" aria-labelledby="features-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="features-title" className="landing-section-title">
              {t('landing.features.title')}
            </h2>
            <p className="landing-section-sub mx-auto">{t('landing.features.sub')}</p>
          </div>
          <div className="landing-features mt-[var(--spacing-6)]">
            {features.map((f) => (
              <Link
                key={f.title}
                to={f.to}
                className="surface-card card-link min-w-0 p-[var(--spacing-4)]"
                aria-label={`${f.title}: ${f.cta}`}
              >
                <span className="landing-feature-icon" aria-hidden="true">
                  <NavIcon name={f.icon} size={20} />
                </span>
                <strong className="mt-[var(--spacing-3)] block text-[length:var(--text-h3)]">{f.title}</strong>
                <span className="landing-feature-what">{f.what}</span>
                <span className="landing-feature-why">
                  <strong>{t('landing.features.whyPrefix')} </strong>
                  {f.why}
                </span>
                <FeatureMini kind={f.mini} />
                <span
                  className="mt-[var(--spacing-3)] inline-flex items-center gap-[var(--spacing-1)] text-[length:var(--text-label)] font-bold"
                  style={{ color: 'var(--color-text-brand)' }}
                >
                  {f.cta}
                  <span aria-hidden="true">
                    <ArrowIcon />
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </section>

        {/* ---- Product showcase: the actual experience ---- */}
        <section id="product" aria-labelledby="product-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="product-title" className="landing-section-title">
              {t('landing.showcase.title')}
            </h2>
            <p className="landing-section-sub mx-auto">{t('landing.showcase.sub')}</p>
          </div>
          <div className="landing-showcase mt-[var(--spacing-6)]">
            <div className="min-w-0">
              <ul className="landing-annot-list">
                {annotations.map((a) => (
                  <li key={a.key}>
                    <span className="landing-annot-key">{a.key}</span>
                    <span className="text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                      {a.body}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="control-row mt-[var(--spacing-5)]">
                <Link to="/jobs" className="btn btn-primary">
                  {t('landing.showcase.cta1')}
                </Link>
                <Link to="/library" className="btn btn-secondary">
                  {t('landing.showcase.cta2')}
                </Link>
              </div>
            </div>
            <div className="landing-monitor" role="img" aria-label={t('landing.showcase.monitorAria')}>
              <div className="landing-tabs" aria-hidden="true">
                {[
                  t('landing.mini.tab1'),
                  t('landing.mini.tab2'),
                  t('landing.mini.tab3'),
                  t('landing.mini.tab4'),
                  t('landing.mini.tab5'),
                ].map((tab, i) => (
                  <span key={tab} className={i === 1 ? 'badge badge-accent' : 'badge'}>
                    {tab}
                  </span>
                ))}
              </div>
              <div aria-hidden="true">
                <div className="landing-chunk">
                  <div className="min-w-0">
                    <p className="landing-chunk-id">{t('landing.showcase.chunkId1')}</p>
                    <p dir="ltr" lang="en" className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ textAlign: 'left', color: 'var(--color-text-secondary)' }}>
                      The map, he said, was not the territory.
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="landing-chunk-id">{t('landing.showcase.trLabel')}</p>
                    <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-primary)' }}>
                      گفت نقشه، خودِ سرزمین نیست.
                    </p>
                  </div>
                </div>
                <div className="landing-chunk">
                  <div className="min-w-0">
                    <p className="landing-chunk-id">{t('landing.showcase.chunkId2')}</p>
                    <p dir="ltr" lang="en" className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ textAlign: 'left', color: 'var(--color-text-secondary)' }}>
                      But every traveler needs one to begin.
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="landing-chunk-id">{t('landing.showcase.trReview')}</p>
                    <p className="mt-[var(--spacing-1)] text-[length:var(--text-small)]" style={{ color: 'var(--color-text-primary)' }}>
                      <span className="flag-pill">{t('landing.showcase.flagReview')}</span>
                      اما هر مسافری برای شروع به یکی نیاز دارد.
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-[var(--spacing-2)] p-[var(--spacing-3)] px-[var(--spacing-4)]">
                  <span className="badge badge-success">{t('landing.showcase.badge1')}</span>
                  <span className="badge badge-info">{t('landing.showcase.badge2')}</span>
                  <span className="badge">{t('landing.showcase.badge3')}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---- How it works: the real 4-step workflow ---- */}
        <section id="how" aria-labelledby="how-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="how-title" className="landing-section-title">
              {t('landing.steps.title')}
            </h2>
          </div>
          <ol className="landing-steps mt-[var(--spacing-6)]">
            {steps.map((s) => (
              <li key={s.index} className="surface-card min-w-0 p-[var(--spacing-4)]">
                <span className="landing-step-index" aria-hidden="true">
                  {s.index}
                </span>
                <strong className="mt-[var(--spacing-2)] block text-[length:var(--text-h3)]">{s.title}</strong>
                <span
                  className="mt-[var(--spacing-2)] block text-[length:var(--text-small)]"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {s.body}
                </span>
              </li>
            ))}
          </ol>
        </section>

        {/* ---- Use cases ---- */}
        <section aria-labelledby="cases-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="cases-title" className="landing-section-title">
              {t('landing.cases.title')}
            </h2>
          </div>
          <div className="landing-cases mt-[var(--spacing-6)]">
            {cases.map((c) => (
              <div key={c.title} className="surface-card min-w-0 p-[var(--spacing-4)]">
                <strong className="block text-[length:var(--text-h3)]">{c.title}</strong>
                <span
                  className="mt-[var(--spacing-2)] block text-[length:var(--text-small)]"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {c.body}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ---- Why KALIMA: honest differentiation ---- */}
        <section aria-labelledby="why-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="why-title" className="landing-section-title">
              {t('landing.why.title')}
            </h2>
            <p className="landing-section-sub mx-auto">{t('landing.why.sub')}</p>
          </div>
          <div className="landing-compare mt-[var(--spacing-6)]">
            <div className="landing-compare-row" style={{ background: 'var(--color-surface-elevated)' }}>
              <strong className="landing-compare-dim">{t('landing.why.headDim')}</strong>
              <strong className="landing-compare-dim">{t('landing.why.headKalima')}</strong>
            </div>
            {compare.map((r) => (
              <div key={r.dim} className="landing-compare-row">
                <div className="min-w-0">
                  <span className="landing-compare-dim">{r.dim}</span>
                  <span className="landing-compare-generic mt-[var(--spacing-1)] block">{r.generic}</span>
                </div>
                <span className="landing-compare-kalima">{r.kalima}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ---- Formats: the 9 registered outputs ---- */}
        <section aria-labelledby="formats-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <h2 id="formats-title" className="landing-section-title">
            {t('landing.formats.title')}
          </h2>
          <p className="landing-section-sub">{t('landing.formats.sub')}</p>
          <div className="mt-[var(--spacing-4)] grid gap-[var(--spacing-2)] sm:grid-cols-2 lg:grid-cols-3">
            {formats.map((f) => (
              <div key={f.name} className="surface-card min-w-0 p-[var(--spacing-3)]">
                <strong className="block text-[length:var(--text-small)]">{f.name}</strong>
                <span className="text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
                  {f.hint}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-[var(--spacing-3)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
            {t('landing.formats.note')}
          </p>
        </section>

        {/* ---- Security ---- */}
        <section id="security" aria-labelledby="security-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <h2 id="security-title" className="landing-section-title">
            {t('landing.security.title')}
          </h2>
          <div className="mt-[var(--spacing-4)] grid gap-[var(--spacing-3)] lg:grid-cols-3">
            {security.map((item) => (
              <div key={item.title} className="surface-card min-w-0 p-[var(--spacing-4)]">
                <span style={{ color: 'var(--color-success)' }}>
                  <CheckIcon />
                </span>
                <strong className="mt-[var(--spacing-2)] block text-[length:var(--text-small)]">{item.title}</strong>
                <span className="mt-[var(--spacing-1)] block text-[length:var(--text-small)]" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.body}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ---- Pricing: the real catalog from the account portal ---- */}
        <section id="pricing" aria-labelledby="pricing-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="mx-auto max-w-[40rem] text-center">
            <h2 id="pricing-title" className="landing-section-title">
              {t('landing.pricing.title')}
            </h2>
            <p className="landing-section-sub mx-auto">{t('landing.pricing.sub')}</p>
          </div>
          <div className="landing-plans mt-[var(--spacing-6)]">
            {plans.map((p) => (
              <div key={p.id} className="surface-card min-w-0 flex flex-col p-[var(--spacing-4)]">
                <strong className="block text-[length:var(--text-h3)]">{p.name}</strong>
                <span className="text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
                  {p.blurb}
                </span>
                <p className="landing-price">
                  <span className="landing-price-amount">{p.price}</span>
                  {p.per ? <span className="landing-price-per">{p.per}</span> : null}
                </p>
                <ul className="landing-plan-list">
                  {p.features.map((f) => (
                    <li key={f}>
                      <span style={{ color: 'var(--color-success)', flex: 'none' }}>
                        <CheckIcon />
                      </span>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link to={p.to} className={p.id === 'free' ? 'btn btn-primary mt-auto' : 'btn btn-secondary mt-auto'}>
                  {p.cta}
                </Link>
              </div>
            ))}
          </div>
        </section>

        {/* ---- FAQ ---- */}
        <section id="faq" aria-labelledby="faq-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <h2 id="faq-title" className="landing-section-title">
            {t('landing.faq.title')}
          </h2>
          <p className="landing-section-sub">{t('landing.faq.sub')}</p>
          <div className="landing-faq mt-[var(--spacing-4)]">
            {faqs.map((f) => (
              <details key={f.q}>
                <summary>{f.q}</summary>
                <p className="landing-faq-body">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* ---- Final CTA ---- */}
        <section aria-labelledby="cta-title" className="landing-section mt-[var(--spacing-12)]" data-reveal>
          <div className="landing-band">
            <CtaBookArt />
            <h2 id="cta-title" className="landing-band-title">
              {t('landing.band.title')}
            </h2>
            <p className="landing-band-sub">{t('landing.band.sub')}</p>
            <div className="control-row mt-[var(--spacing-5)] justify-center">
              <Link to="/workspace" className="btn btn-primary">
                {t('landing.band.cta1')}
              </Link>
              <Link to="/convert" className="btn btn-secondary">
                {t('landing.band.cta2')}
              </Link>
            </div>
          </div>
        </section>

        {/* ---- Footer: only routes that exist ---- */}
        <footer className="landing-foot mt-[var(--spacing-8)]" aria-label={t('landing.footer.footAria')}>
          <div className="min-w-0">
            <span className="flex min-w-0 items-center gap-[var(--spacing-2)]">
              <KalimaMark size={28} />
              <strong className="text-[length:var(--text-small)]">KALIMA</strong>
            </span>
            <p className="mt-[var(--spacing-2)] text-[length:var(--text-caption)]" style={{ color: 'var(--color-text-muted)' }}>
              {t('landing.footer.tagline')}
            </p>
          </div>
          <nav aria-label={t('landing.footer.productH')}>
            <p className="landing-foot-head">{t('landing.footer.productH')}</p>
            <ul className="landing-foot-group">
              {footerAnchors.map((a) => (
                <li key={a.href}>
                  <a href={a.href}>{a.label}</a>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label={t('landing.footer.appH')}>
            <p className="landing-foot-head">{t('landing.footer.appH')}</p>
            <ul className="landing-foot-group">
              <li><Link to="/workspace">{t('landing.footer.appWorkspace')}</Link></li>
              <li><Link to="/jobs">{t('landing.footer.appJobs')}</Link></li>
              <li><Link to="/library">{t('landing.footer.appLibrary')}</Link></li>
              <li><Link to="/convert">{t('landing.footer.appConvert')}</Link></li>
              <li><Link to="/account">{t('landing.footer.appAccount')}</Link></li>
            </ul>
          </nav>
        </footer>
        <p className="landing-fineprint">{t('landing.pricing.footnote')}</p>
      </div>
    </main>
  )
}
