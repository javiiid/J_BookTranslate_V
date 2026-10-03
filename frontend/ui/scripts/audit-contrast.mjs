/**
 * Render the Reader and Account pages to static HTML and measure the contrast of
 * every text element.
 *
 * The complaint is "the text is not readable", which is a contrast claim, and a
 * contrast claim has to be measured rather than reasoned about. No browser is
 * available in this session and Chromium cannot be downloaded, so this does the
 * next most rigorous thing:
 *
 *   1. build the real components with Vite into a library bundle
 *   2. render them to HTML with react-dom/server, against the payloads the live
 *      backend actually returned (scripts/page-data.json)
 *   3. wrap that in the real built stylesheet
 *   4. walk the result, and for every element containing text, resolve its
 *      colour and the colour behind it by applying the cascade
 *
 * A hand-written class list would test the wrong thing: the HTML comes from the
 * same JSX the browser runs.
 */
import { build } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync, readdirSync, rmSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')
const outDir = join(ui, 'node_modules', '.tmp', 'audit')

/* ------------------------------------------------------------------ */
/* 1. Build the pages into a library so Node can import real JSX        */
/* ------------------------------------------------------------------ */

rmSync(outDir, { recursive: true, force: true })

// A real entry file rather than a virtual module: `Cannot resolve entry module
// virtual:audit`, and the audit has to run the same JSX the browser runs.
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: {
      entry: join(here, 'audit-entry.ts'),
      formats: ['es'],
      fileName: () => 'pages.js',
    },
    rollupOptions: {
      external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/server', '@tanstack/react-query', 'react-router-dom', 'react-router'],
    },
    minify: false,
  },
})

const pagesUrl = new URL(`file://${join(outDir, 'pages.js').replace(/\\/g, '/')}`).href
const { ReaderPage, AccountPage, DashboardPage, WorkspacePage, LibraryPage, AppShell } =
  await import(pagesUrl)

/* ------------------------------------------------------------------ */
/* 2. Stub the network with the captured payloads                      */
/* ------------------------------------------------------------------ */

const PAYLOADS = JSON.parse(readFileSync(join(here, 'page-data.json'), 'utf8'))
const requested = []

globalThis.fetch = async (input) => {
  const url = String(input)
  requested.push(url)
  const body = PAYLOADS[url]
  if (body === undefined) {
    return new Response(JSON.stringify({ error: `no stub for ${url}` }), { status: 404 })
  }
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}
globalThis.localStorage = { getItem: () => null, setItem: () => {} }

/* ------------------------------------------------------------------ */
/* 3. Render                                                           */
/* ------------------------------------------------------------------ */


const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
})

/**
 * Seed the cache with the captured payloads.
 *
 * Without this the audit measures nothing useful. `renderToStaticMarkup` is
 * synchronous and react-query resolves asynchronously, so every page rendered
 * in its loading state: the Reader came out as 4,588 characters, which is the
 * sidebar plus a skeleton, and the measured contrast was all shell. It reported
 * zero failures because there was no real text to fail.
 */
// The stub is keyed on the full request path, which for the reader includes
// /api: the frontend calls `/api${job.reader}/chapters`.
const READER_ID = '040061b0658b'
const READER = `/reader/${READER_ID}`
const CHAPTER = PAYLOADS[`/api${READER}/chapters`].items[0].id

const SEED = [
  [['health'], PAYLOADS['/api/health']],
  [['summary'], PAYLOADS['/api/dashboard/summary']],
  [['jobs'], PAYLOADS['/api/jobs']],
  [['models'], PAYLOADS['/api/models']],
  [['languages'], PAYLOADS['/api/languages']],
  [['provider-config'], PAYLOADS['/api/provider-config']],
  [['portal'], PAYLOADS['/api/account/portal']],
  [['analytics'], PAYLOADS['/api/analytics/overview']],
  [['reader-settings'], PAYLOADS['/api/reader/settings']],
  [['reader-chapters', READER_ID], PAYLOADS[`/api${READER}/chapters`]],
  [['reader-chapter', READER_ID, CHAPTER], PAYLOADS[`/api${READER}/chapters/${CHAPTER}`]],
  [['reader-blocks', READER_ID, CHAPTER], PAYLOADS[`/api${READER}/chapters/${CHAPTER}/blocks`]],
]

for (const [key, data] of SEED) queryClient.setQueryData(key, data)
console.log(`  seeded ${SEED.length} quer(ies) so the pages render with data`)

/**
 * Render the page inside the app shell, the way `main.tsx` does.
 *
 * The shell is not decoration here: it puts `background: var(--color-background)`
 * on the root element, which is the surface every measurement is taken against.
 * Rendering a page bare gave the audit no background to find, and it fell back
 * to white for both themes.
 */
function renderWithShell(Component, pattern, entry) {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: [entry] },
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          AppShell,
          null,
          createElement(
            Routes,
            null,
            createElement(Route, { path: pattern, element: createElement(Component) }),
            createElement(Route, { path: '*', element: createElement(Component) }),
          ),
        ),
      ),
    ),
  )
}

/**
 * Render a page inside the route it is mounted at.
 *
 * `useParams()` reads from the router context, and rendering a component bare
 * gives it `id === ''`, which disables every query. The Reader came out as 4,588
 * characters: the sidebar and nothing else, so the audit reported no contrast
 * failures because there was no text to fail on. Declaring the route the same
 * way App.tsx does makes the params arrive.
 */

// Routes declared the same way App.tsx declares them, so `useParams` resolves
// and the pages fetch the same data the browser would.
const ROUTES = {
  reader: ['/reader/:id', '/reader/040061b0658b', ReaderPage],
  account: ['/account', '/account', AccountPage],
  dashboard: ['/', '/', DashboardPage],
  workspace: ['/workspace', '/workspace', WorkspacePage],
  library: ['/library', '/library', LibraryPage],
}

const rendered = {}
for (const [name, [pattern, entry, Component]] of Object.entries(ROUTES)) {
  try {
    const html = renderWithShell(Component, pattern, entry)
    rendered[name] = html
    console.log(`  rendered ${name}: ${html.length} chars`)
  } catch (error) {
    console.error(`  ${name}: RENDER THREW -> ${error instanceof Error ? error.message : String(error)}`)
    rendered[name] = null
  }
}

if (process.env.AUDIT_DEBUG) {
  for (const [name, html] of Object.entries(rendered)) {
    if (!html) continue
    console.log(`\n--- ${name}: first 900 chars ---`)
    console.log(html.slice(0, 900))
  }
}

/* ------------------------------------------------------------------ */
/* 4. Load the real stylesheet                                         */
/* ------------------------------------------------------------------ */

const assetsDir = join(ui, 'dist', 'assets')
const cssFile = readdirSync(assetsDir).find((name) => name.endsWith('.css'))
if (!cssFile) {
  console.error('  no built CSS; run `npm run build` first')
  process.exit(1)
}
const css = readFileSync(join(assetsDir, cssFile), 'utf8')

const RULES = []
for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
  const declarations = {}
  for (const declaration of match[2].split(';')) {
    const index = declaration.indexOf(':')
    if (index === -1) continue
    declarations[declaration.slice(0, index).trim()] = declaration.slice(index + 1).trim()
  }
  if (Object.keys(declarations).length === 0) continue
  for (const raw of match[1].split(',')) {
    const selector = raw.trim()
    if (selector && !selector.startsWith('@')) {
      RULES.push({ selector, declarations, order: RULES.length })
    }
  }
}

/**
 * Custom property values, per theme.
 *
 * The first version of this resolved `var(--x)` to the *name* `--x` rather than
 * its value, so every measurement silently produced nothing. Looking the name up
 * is the whole job.
 *
 * Kept as two maps because the whole point of the audit is to check both themes:
 * the same class resolves to a different colour under `.dark`, and a page can be
 * perfectly readable in one and invisible in the other.
 */
function collectVariables(selector) {
  const map = new Map()
  for (const rule of RULES) {
    if (rule.selector !== selector) continue
    for (const [name, value] of Object.entries(rule.declarations)) {
      if (name.startsWith('--')) map.set(name, value)
    }
  }
  return map
}

const THEMES = {
  light: { label: 'light', vars: collectVariables(':root'), active: false },
  dark: { label: 'dark', vars: collectVariables('.dark'), active: false },
}
// Whatever :root already declares, .dark inherits and only overrides part of it.
for (const [name, value] of THEMES.light.vars) {
  if (!THEMES.dark.vars.has(name)) THEMES.dark.vars.set(name, value)
}

let currentTheme = THEMES.light

function lookupVariable(name) {
  const value = currentTheme.vars.get(name)
  return value === undefined ? null : value
}

function specificity(selector) {
  const ids = (selector.match(/#[\w-]+/g) ?? []).length
  const classes = (selector.match(/\.[\w-]+/g) ?? []).length
  const pseudo = (selector.match(/::?[a-z-]+(\([^)]*\))?/gi) ?? []).length
  const elements = (selector.replace(/[.#:][^{]*/g, '').match(/(^|[\s>])[a-z][\w-]*/gi) ?? []).length
  return ids * 10000 + (classes + pseudo) * 100 + elements
}

function matches(selector, element) {
  const cleaned = selector
    .replace(/::[a-z-]+/gi, '')
    .replace(/\[[^\]]*\]/g, '')
    .replace(/:[a-z-]+(\([^)]*\))?/gi, '')
    .trim()
  if (!cleaned) return false
  for (const part of cleaned.split(/\s+|>/).filter(Boolean)) {
    if (part === '*') continue
    const wanted = part.replace(/^\./, '').toLowerCase()
    if (part.startsWith('.')) {
      if (!element.classes.includes(wanted)) return false
    } else if (part === wanted) {
      // exact tag
    } else if (['html', 'body'].includes(wanted)) {
      if (element.tag !== wanted) return false
    } else {
      return false
    }
  }
  return true
}

function resolveVar(value, seen = new Set()) {
  if (!value) return null
  const text = value.trim()
  if (!text.startsWith('var(')) return text
  const inner = text.slice(4, -1)
  const comma = splitTopLevel(inner)
  const variable = comma[0].trim()
  if (seen.has(variable)) return null
  const next = new Set(seen).add(variable)
  const resolved = lookupVariable(variable)
  if (resolved !== null) return resolveVar(resolved, next)
  return comma[1] ? resolveVar(comma[1].trim(), next) : null
}

function splitTopLevel(text) {
  const parts = []
  let depth = 0
  let current = ''
  for (const char of text) {
    if (char === '(') depth++
    if (char === ')') depth--
    if (char === ',' && depth === 0) {
      parts.push(current)
      current = ''
    } else {
      current += char
    }
  }
  parts.push(current)
  return parts
}

/** Resolve a property for one element, letting ancestors cascade. */
function computedAt(element, ancestors, property) {
  const chain = [...ancestors, element]
  let best = null
  for (const rule of RULES) {
    const value = rule.declarations[property]
    if (!value) continue
    for (let i = chain.length - 1; i >= 0; i--) {
      if (matches(rule.selector, chain[i])) {
        const score = specificity(rule.selector) + i
        if (!best || score >= best.score) best = { score, value }
        break
      }
    }
  }
  return best ? resolveVar(best.value) : null
}

function declaredValue(element, property) {
  return element.style[property] ? resolveVar(element.style[property]) : null
}

/* ------------------------------------------------------------------ */
/* 5. Walk and measure                                                 */
/* ------------------------------------------------------------------ */

const VOID = new Set(['br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'path', 'rect', 'circle', 'line', 'polygon'])

function parse(html) {
  const root = { tag: '#root', classes: [], children: [], parent: null, text: '', style: {} }
  const stack = [root]
  for (const match of html.matchAll(/<\/?([a-zA-Z][\w-]*)((?:"[^"]*"|'[^']*'|[^>])*)>|([^<]+)/g)) {
    const [raw, tag, attrs, textChunk] = match
    if (textChunk !== undefined) {
      if (textChunk.trim()) stack[stack.length - 1].text += textChunk
      continue
    }
    const name = tag.toLowerCase()
    if (VOID.has(name)) continue
    if (raw.startsWith('</')) {
      if (stack.length > 1) stack.pop()
      continue
    }
    const classAttr = /class="([^"]*)"/.exec(attrs ?? '')
    const element = {
      tag: name,
      classes: classAttr ? classAttr[1].split(/\s+/).filter(Boolean) : [],
      children: [],
      parent: stack[stack.length - 1],
      text: '',
      style: {},
    }
    const styleAttr = /style="([^"]*)"/.exec(attrs ?? '')
    if (styleAttr) {
      for (const declaration of styleAttr[1].split(';')) {
        const index = declaration.indexOf(':')
        if (index === -1) continue
        element.style[declaration.slice(0, index).trim()] = declaration.slice(index + 1).trim()
      }
    }
    stack[stack.length - 1].children.push(element)
    if (!raw.endsWith('/>')) stack.push(element)
  }
  return root
}

function toRgb(value) {
  if (!value) return null
  let text = value.trim().toLowerCase()
  if (text === 'transparent') return null
  // A `const` here would be reassigned on the next line, which is a warning in
  // any linter and a bug the moment someone reads it as immutable.
  const NAMED = { white: '#ffffff', black: '#000000' }
  text = NAMED[text] ?? text
  const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/.exec(text)
  if (!match) return null
  const hex = match[1].length === 3 ? [...match[1]].map((c) => c + c).join('') : match[1]
  return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16))
}

function luminance([r, g, b]) {
  const channel = (c) => {
    const v = c / 255
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(a, b) {
  const la = luminance(a)
  const lb = luminance(b)
  const [hi, lo] = la > lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}

const measurements = []

const measure = (page, html) => {
  const root = parse(html)

  /**
   * The nearest opaque background behind an element.
   *
   * `background` and `background-color` are both consulted, and the search walks
   * from the element outwards. An earlier version stopped at the first ancestor
   * that declared a background, which for `.btn-primary` is the element itself:
   * its `background: var(--color-primary)` resolved to white under the light
   * theme while its text was the dark theme's near-white, producing a
   * "1.00:1 white on white" reading that does not exist in the browser.
   */
  const effectiveBackground = (element, ancestors) => {
    const chain = [...ancestors, element]
    for (let i = chain.length - 1; i >= 0; i--) {
      const target = chain[i]
      const own = ancestors.slice(0, i)
      for (const property of ['background-color', 'background']) {
        const declared = declaredValue(target, property)
        const value = declared ?? computedAt(target, own, property)
        const resolved = resolveVar(value ?? '', new Set())
        if (resolved && toRgb(resolved) && resolved.toLowerCase() !== 'transparent') {
          return resolved
        }
      }
    }
    return '#ffffff'
  }

  const effectiveColour = (element, ancestors) => {
    const chain = [...ancestors, element]
    for (let i = chain.length - 1; i >= 0; i--) {
      const declared = declaredValue(chain[i], 'color')
      if (declared && toRgb(declared)) return declared
      const computed = computedAt(chain[i], chain.slice(0, i), 'color')
      if (computed && toRgb(computed)) return computed
    }
    return null
  }

  const effectiveFontSize = (element, ancestors) => {
    const chain = [...ancestors, element]
    for (let i = chain.length - 1; i >= 0; i--) {
      const declared = declaredValue(chain[i], 'font-size')
      const value = declared ?? computedAt(chain[i], chain.slice(0, i), 'font-size')
      if (!value) continue
      const rem = /^([\d.]+)rem$/.exec(value)
      if (rem) return parseFloat(rem[1]) * 16
      const px = /^([\d.]+)px$/.exec(value)
      if (px) return parseFloat(px[1])
      const bare = parseFloat(value)
      if (!Number.isNaN(bare)) return bare
    }
    return 16
  }

  const visit = (element, ancestors) => {
    if (element.text.trim() && !['svg', 'path', 'rect', 'g'].includes(element.tag)) {
      const colour = effectiveColour(element, ancestors)
      const background = effectiveBackground(element, ancestors)
      const fg = toRgb(colour)
      const bg = toRgb(background)
      if (fg && bg) {
        measurements.push({
          theme: currentTheme.label,
          page,
          tag: element.tag,
          classes: element.classes.join(' '),
          colour,
          background,
          fontSize: effectiveFontSize(element, ancestors),
          ratio: contrast(fg, bg),
          text: element.text.trim().slice(0, 44),
        })
      }
    }
    for (const child of element.children) visit(child, [...ancestors, element])
  }

  visit(root, [])
}

for (const theme of Object.values(THEMES)) {
  currentTheme = theme
  console.log(`  theme ${theme.label}: ${theme.vars.size} custom propert(ies) available`)
  for (const [page, html] of Object.entries(rendered)) {
    if (html) measure(page, html)
  }
}

measurements.sort((a, b) => a.ratio - b.ratio)

console.log('')
console.log('=== text contrast, worst first ===')
console.log('-'.repeat(80))
for (const item of measurements.slice(0, 22)) {
  const flag = item.ratio < 3 ? 'FAIL' : item.ratio < 4.5 ? 'large' : 'ok'
  console.log(
    `  ${flag.padEnd(6)} ${item.ratio.toFixed(2).padStart(6)}:1 ${String(Math.round(item.fontSize)).padStart(3)}px  ` +
      `${item.theme}/${item.page}/${item.tag}  "${item.text}"`,
  )
  console.log(`         colour ${item.colour} on ${item.background}   .${item.classes || '(no class)'}`)
}
console.log('-'.repeat(80))
const failing = measurements.filter((m) => m.ratio < 4.5)
const unreadable = measurements.filter((m) => m.ratio < 3)
const tiny = measurements.filter((m) => m.fontSize < 12)
console.log(`  ${measurements.length} text element(s) measured across both themes`)
console.log(`  ${unreadable.length} below 3:1   (unreadable)`)
console.log(`  ${failing.length} below 4.5:1  (fails AA for body text)`)
console.log(`  ${tiny.length} below 12px`)
if (existsSync(outDir)) rmSync(outDir, { recursive: true, force: true })
process.exit(unreadable.length > 0 ? 1 : 0)
