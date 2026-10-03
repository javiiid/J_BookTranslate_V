/**
 * Render the Reader and Account pages to PNG so they can be looked at.
 *
 * There is no browser in this session and Chromium cannot be downloaded, so the
 * pages are rendered to HTML, written to a file, and printed. The output is the
 * text as the browser would lay it out, which is what actually settles "is this
 * readable" when no screenshot is available.
 *
 * Both themes, because a page can be fine in one and unusable in the other.
 */
import { build } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const ui = join(here, '..')
const outDir = join(ui, 'node_modules', '.tmp', 'preview')

rmSync(outDir, { recursive: true, force: true })
await build({
  root: ui,
  logLevel: 'error',
  build: {
    outDir,
    emptyOutDir: true,
    lib: { entry: join(here, 'audit-entry.ts'), formats: ['es'], fileName: () => 'pages.js' },
    rollupOptions: {
      external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/server', '@tanstack/react-query', 'react-router-dom', 'react-router'],
    },
    minify: false,
  },
})

const { ReaderPage, AccountPage, DashboardPage, AppShell } = await import(
  new URL(`file://${join(outDir, 'pages.js').replace(/\\/g, '/')}`).href
)

const PAYLOADS = JSON.parse(readFileSync(join(here, 'page-data.json'), 'utf8'))
globalThis.fetch = async (input) => {
  const body = PAYLOADS[String(input)]
  return new Response(body === undefined ? '{}' : JSON.stringify(body), {
    status: body === undefined ? 404 : 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
globalThis.localStorage = { getItem: () => null, setItem: () => {} }

const READER_ID = '040061b0658b'
const READER = `/reader/${READER_ID}`
const CHAPTER = PAYLOADS[`/api${READER}/chapters`].items[0].id

function makeClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  const seed = [
    [['health'], PAYLOADS['/api/health']],
    [['summary'], PAYLOADS['/api/dashboard/summary']],
    [['jobs'], PAYLOADS['/api/jobs']],
    [['models'], PAYLOADS['/api/models']],
    [['provider-config'], PAYLOADS['/api/provider-config']],
    [['portal'], PAYLOADS['/api/account/portal']],
    [['analytics'], PAYLOADS['/api/analytics/overview']],
    [['reader-settings'], PAYLOADS['/api/reader/settings']],
    [['reader-chapters', READER_ID], PAYLOADS[`/api${READER}/chapters`]],
    [['reader-chapter', READER_ID, CHAPTER], PAYLOADS[`/api${READER}/chapters/${CHAPTER}`]],
    [['reader-blocks', READER_ID, CHAPTER], PAYLOADS[`/api${READER}/chapters/${CHAPTER}/blocks`]],
  ]
  for (const [key, data] of seed) client.setQueryData(key, data)
  return client
}

const assetsDir = join(ui, 'dist', 'assets')
const cssFile = readdirSync(assetsDir).find((n) => n.endsWith('.css'))
const css = readFileSync(join(assetsDir, cssFile), 'utf8')

const PAGES = {
  reader: { pattern: '/reader/:id', entry: `/reader/${READER_ID}`, Component: ReaderPage },
  account: { pattern: '/account', entry: '/account', Component: AccountPage },
  dashboard: { pattern: '/', entry: '/', Component: DashboardPage },
}

const previewDir = join(here, 'preview')
mkdirSync(previewDir, { recursive: true })

for (const [name, { pattern, entry, Component }] of Object.entries(PAGES)) {
  const client = makeClient()
  const body = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: [entry] },
      createElement(
        QueryClientProvider,
        { client },
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

  // The stylesheet is inlined so the file is self-contained: opening it shows the
  // real design system rather than unstyled markup.
  const html = `<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>KALIMA — ${name} (light)</title>
<style>${css}</style>
</head>
<body>${body}</body>
</html>`

  const light = join(previewDir, `${name}-light.html`)
  writeFileSync(light, html, 'utf8')

  // The dark theme needs the class on <html>, which server rendering cannot set.
  const dark = join(previewDir, `${name}-dark.html`)
  writeFileSync(dark, html.replace('<html lang="fa" dir="rtl">', '<html lang="fa" dir="rtl" class="dark">'), 'utf8')

  console.log(`  ${name}: ${body.length} chars -> ${name}-light.html, ${name}-dark.html`)
}

rmSync(outDir, { recursive: true, force: true })
console.log(`\n  open: ${previewDir}`)
